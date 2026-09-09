"""Automatic BEP20 USDT sweep from derived advertiser addresses to treasury.

Security model:
* ``ACCOUNT_XPRV`` is the only private key material held by the service.
  It is read from the environment and never persisted elsewhere.
* The gas wallet (``BSC_GAS_WALLET_PRIVATE_KEY``) is a separate hot wallet
  whose only job is to send small BNB amounts to derived addresses so they
  can pay for the USDT sweep transaction.
* After the sweep, any leftover BNB above a configurable dust threshold is
  returned to the gas wallet.
* All on-chain operations are recorded in the ``bep20_sweeps`` table.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from app.config import settings
from app.core.errors import ConfigurationError
from app.models.finance import Bep20Sweep, WalletAddress

logger = logging.getLogger(__name__)

# Minimal ERC-20 ABI for balanceOf and transfer.
ERC20_ABI: list[dict[str, Any]] = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
]

USDT_DECIMALS = 18
USDT_WEI = Decimal(10) ** USDT_DECIMALS
BNB_DECIMALS = 18
BNB_WEI = Decimal(10) ** BNB_DECIMALS

BSC_PATH = "m/44'/60'/0'/0/{index}"


def _assert_configured() -> None:
    if not settings.ACCOUNT_XPRV:
        raise ConfigurationError("BEP20 sweep requires ACCOUNT_XPRV.")
    if not settings.BSC_GAS_WALLET_PRIVATE_KEY:
        raise ConfigurationError("BEP20 sweep requires BSC_GAS_WALLET_PRIVATE_KEY.")
    if not settings.BSC_TREASURY_ADDRESS:
        raise ConfigurationError("BEP20 sweep requires BSC_TREASURY_ADDRESS.")


def _web3() -> Any:
    from web3 import Web3

    return Web3(Web3.HTTPProvider(settings.BSC_RPC_URL))


def _derive_bsc_keypair(xprv: str, index: int) -> tuple[str, str]:
    """Return (private_key_hex, address) for the given BIP-44 index."""
    from bip_utils import Bip44, Bip44Changes, Bip44Coins

    ctx = Bip44.FromExtendedKey(xprv, Bip44Coins.BINANCE_SMART_CHAIN)
    child = ctx.Change(Bip44Changes.CHAIN_EXT).AddressIndex(index)
    priv = child.PrivateKey().Raw().ToHex()
    addr = child.PublicKey().ToAddress()
    return priv, addr


def _usdt_contract(w3: Any) -> Any:
    from web3 import Web3

    return w3.eth.contract(
        address=Web3.to_checksum_address(settings.USDT_BEP20_CONTRACT),
        abi=ERC20_ABI,
    )


def _account(w3: Any, private_key: str) -> Any:
    from web3 import Web3

    return w3.eth.account.from_key(private_key)


def _gas_wallet_address() -> str:
    w3 = _web3()
    return _account(w3, settings.BSC_GAS_WALLET_PRIVATE_KEY).address


def _bnb_balance(w3: Any, address: str) -> Decimal:
    from web3 import Web3

    balance_wei = w3.eth.get_balance(Web3.to_checksum_address(address))
    return Decimal(balance_wei) / BNB_WEI


def _usdt_balance(w3: Any, address: str) -> Decimal:
    from web3 import Web3

    contract = _usdt_contract(w3)
    balance_wei = contract.functions.balanceOf(Web3.to_checksum_address(address)).call()
    return Decimal(balance_wei) / USDT_WEI


def _estimate_gas_price(w3: Any) -> int:
    """Return a gas price with a small premium to improve inclusion speed."""
    from web3 import Web3

    base = w3.eth.gas_price
    # 10% premium, capped to avoid runaway values.
    return int(min(base * 11 // 10, base + Web3.to_wei(5, "gwei")))


def _send_raw_transaction(
    w3: Any,
    private_key: str,
    to: str,
    value_wei: int = 0,
    data: bytes = b"",
    gas: int | None = None,
) -> str:
    from web3 import Web3

    account = _account(w3, private_key)
    nonce = w3.eth.get_transaction_count(account.address)
    tx: dict[str, Any] = {
        "from": account.address,
        "to": Web3.to_checksum_address(to),
        "value": value_wei,
        "data": data,
        "nonce": nonce,
        "gasPrice": _estimate_gas_price(w3),
        "chainId": w3.eth.chain_id,
    }
    if gas is not None:
        tx["gas"] = gas
    else:
        tx["gas"] = w3.eth.estimate_gas(tx)

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()


def _send_bnb(private_key: str, to: str, amount_bnb: Decimal) -> str:
    w3 = _web3()
    value_wei = int(amount_bnb * BNB_WEI)
    return _send_raw_transaction(w3, private_key, to, value_wei=value_wei, gas=21_000)


def _sweep_usdt(private_key: str, to: str, amount_wei: int) -> str:
    from web3 import Web3

    w3 = _web3()
    contract = _usdt_contract(w3)
    account = _account(w3, private_key)
    tx = contract.functions.transfer(Web3.to_checksum_address(to), amount_wei).build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gasPrice": _estimate_gas_price(w3),
            "gas": settings.BSC_TRANSFER_GAS_LIMIT,
            "chainId": w3.eth.chain_id,
        }
    )
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()


def _calculate_gas_topup(needed_gas_bnb: Decimal) -> Decimal:
    """Send enough BNB to cover the USDT sweep plus a small safety margin."""
    margin = Decimal("0.00005")
    return (needed_gas_bnb + margin).quantize(Decimal("0.000000000000000001"))


async def get_or_create_sweep_record(
    session: Any, deposit: Deposit, wallet: WalletAddress
) -> Bep20Sweep:
    from sqlalchemy import select

    existing = (
        await session.execute(select(Bep20Sweep).where(Bep20Sweep.deposit_id == deposit.id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    record = Bep20Sweep(
        deposit_id=deposit.id,
        derived_address=wallet.address,
        derivation_index=wallet.derivation_index or 0,
        treasury_address=settings.BSC_TREASURY_ADDRESS,
        gross_amount_usd=deposit.gross_amount_usd,
        status="pending",
    )
    session.add(record)
    await session.flush()
    await session.refresh(record)
    return record


async def sweep_bep20_deposit(
    session: Any,
    deposit: Deposit,
    wallet: WalletAddress,
) -> Bep20Sweep:
    """Consolidate one confirmed BEP20 USDT deposit to the treasury.

    Steps:
        1. Derive the private key for the deposit address.
        2. Check USDT balance on-chain.
        3. If the address lacks BNB for gas, top it up from the gas wallet.
        4. Transfer all USDT to the treasury address.
        5. Return any leftover BNB dust to the gas wallet.
    """
    _assert_configured()
    if not settings.ENABLE_BEP20_SWEEP:
        raise ConfigurationError("BEP20 sweep is disabled via ENABLE_BEP20_SWEEP.")

    record = await get_or_create_sweep_record(session, deposit, wallet)
    if record.status in ("swept", "in_progress"):
        return record

    record.status = "in_progress"
    await session.flush()

    try:
        index = wallet.derivation_index
        if index is None:
            raise ValueError("WalletAddress has no derivation_index for BEP20 sweep.")

        private_key, derived_address = _derive_bsc_keypair(settings.ACCOUNT_XPRV, index)
        if derived_address.lower() != wallet.address.lower():
            raise ConfigurationError(
                f"Derived address {derived_address} does not match stored address {wallet.address}."
            )

        w3 = _web3()
        usdt_balance = _usdt_balance(w3, derived_address)
        if usdt_balance <= 0:
            raise ValueError(f"No USDT balance to sweep on {derived_address}.")

        record.gross_amount_usd = usdt_balance
        record.swept_amount_usd = usdt_balance
        await session.flush()

        # Step 1: gas top-up if needed.
        gas_price = _estimate_gas_price(w3)
        gas_cost_wei = gas_price * settings.BSC_TRANSFER_GAS_LIMIT
        gas_cost_bnb = Decimal(gas_cost_wei) / BNB_WEI
        bnb_balance = _bnb_balance(w3, derived_address)

        if bnb_balance < gas_cost_bnb:
            topup = _calculate_gas_topup(gas_cost_bnb)
            tx_hash = _send_bnb(settings.BSC_GAS_WALLET_PRIVATE_KEY, derived_address, topup)
            record.gas_topup_tx_hash = tx_hash
            record.gas_topup_amount_bnb = topup
            logger.info(
                "bep20.gas_topup deposit=%s address=%s amount=%s tx=%s",
                deposit.id,
                derived_address,
                topup,
                tx_hash,
            )

        # Step 2: sweep USDT.
        amount_wei = int(usdt_balance * USDT_WEI)
        sweep_tx = _sweep_usdt(private_key, settings.BSC_TREASURY_ADDRESS, amount_wei)
        record.sweep_tx_hash = sweep_tx
        logger.info(
            "bep20.sweep deposit=%s address=%s amount=%s tx=%s",
            deposit.id,
            derived_address,
            usdt_balance,
            sweep_tx,
        )

        # Step 3: return dust BNB to gas wallet.
        leftover_bnb = _bnb_balance(w3, derived_address)
        if leftover_bnb > settings.BSC_GAS_DUST_BNB:
            return_amount = leftover_bnb - settings.BSC_GAS_DUST_BNB
            gas_wallet_address = _gas_wallet_address()
            return_tx = _send_bnb(private_key, gas_wallet_address, return_amount)
            record.dust_return_tx_hash = return_tx
            record.dust_return_amount_bnb = str(return_amount)
            logger.info(
                "bep20.dust_return deposit=%s address=%s amount=%s tx=%s",
                deposit.id,
                derived_address,
                return_amount,
                return_tx,
            )

        record.status = "swept"
        record.error = None

    except Exception as exc:  # pragma: no cover - on-chain failures are environment-dependent
        record.status = "failed"
        record.error = str(exc)
        logger.exception("bep20.sweep_failed deposit=%s error=%s", deposit.id, exc)

    await session.flush()
    await session.refresh(record)
    return record
