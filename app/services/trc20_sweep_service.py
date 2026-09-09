"""Automatic TRC20 (TRON) USDT sweep from derived advertiser addresses to treasury.

Mirrors ``bep20_sweep_service.py``. Security model:
* ``ACCOUNT_XPRV_TRC20`` is the only private key material held by the service
  for this network. It is read from the environment and never persisted
  elsewhere. It is a *separate* secret from ``ACCOUNT_XPRV`` (BSC) — TRON and
  BSC derive from different BIP-44 coin paths (195' vs 60'), so the same
  extended key cannot be reused across the two.
* The gas wallet (``TRC_GAS_WALLET_PRIVATE_KEY``) is a separate hot wallet
  whose only job is to send small TRX amounts to derived addresses so they
  can pay the transfer's ``fee_limit``.
* After the sweep, any leftover TRX above a configurable dust threshold is
  returned to the gas wallet.
* All on-chain operations are recorded in the ``trc20_sweeps`` table.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from app.config import settings
from app.core.errors import ConfigurationError
from app.models.finance import Deposit, Trc20Sweep, WalletAddress

logger = logging.getLogger(__name__)

USDT_DECIMALS = Decimal("1000000")
TRX_DECIMALS = Decimal("1000000")

TRC20_PATH = "m/44'/195'/0'/0/{index}"


def _assert_configured() -> None:
    if not settings.ACCOUNT_XPRV_TRC20:
        raise ConfigurationError("TRC20 sweep requires ACCOUNT_XPRV_TRC20.")
    if not settings.TRC_GAS_WALLET_PRIVATE_KEY:
        raise ConfigurationError("TRC20 sweep requires TRC_GAS_WALLET_PRIVATE_KEY.")
    if not settings.TRC_TREASURY_ADDRESS:
        raise ConfigurationError("TRC20 sweep requires TRC_TREASURY_ADDRESS.")
    if not settings.TRONGRID_API_KEY:
        raise ConfigurationError("TRC20 sweep requires TRONGRID_API_KEY.")


def _tron_client() -> Any:
    from tronpy import Tron
    from tronpy.providers import HTTPProvider

    provider = HTTPProvider(
        endpoint_uri=settings.TRONGRID_BASE_URL,
        api_key=settings.TRONGRID_API_KEY,
    )
    return Tron(provider=provider)


def _derive_tron_keypair(xprv: str, index: int) -> tuple[bytes, str]:
    """Return (private_key_bytes, address) for the given BIP-44 index."""
    from bip_utils import Bip44, Bip44Changes, Bip44Coins

    ctx = Bip44.FromExtendedKey(xprv, Bip44Coins.TRON)
    child = ctx.Change(Bip44Changes.CHAIN_EXT).AddressIndex(index)
    priv = child.PrivateKey().Raw().ToBytes()
    addr = child.PublicKey().ToAddress()
    return priv, addr


def _usdt_contract(client: Any) -> Any:
    return client.get_contract(settings.USDT_TRC20_CONTRACT)


def _usdt_balance(client: Any, address: str) -> Decimal:
    contract = _usdt_contract(client)
    balance = int(contract.functions.balanceOf(address))
    return Decimal(balance) / USDT_DECIMALS


def _trx_balance(client: Any, address: str) -> Decimal:
    balance_sun = client.get_account_balance(address)
    return Decimal(str(balance_sun))


def _gas_wallet_address(client: Any) -> str:
    from tronpy.keys import PrivateKey

    key = PrivateKey(bytes.fromhex(settings.TRC_GAS_WALLET_PRIVATE_KEY.removeprefix("0x")))
    return key.public_key.to_base58check_address()


def _send_trx(client: Any, private_key_hex: str, to: str, amount_trx: Decimal) -> str:
    from tronpy.keys import PrivateKey

    key = PrivateKey(bytes.fromhex(private_key_hex.removeprefix("0x")))
    from_address = key.public_key.to_base58check_address()
    amount_sun = int(amount_trx * TRX_DECIMALS)
    txn = (
        client.trx.transfer(from_address, to, amount_sun)
        .build()
        .sign(key)
    )
    result = txn.broadcast()
    return result.get("txid") or result.get("id") or str(result)


def _sweep_usdt(client: Any, private_key_bytes: bytes, from_address: str, to: str, amount_wei: int) -> str:
    from tronpy.keys import PrivateKey

    contract = _usdt_contract(client)
    key = PrivateKey(private_key_bytes)
    txn = (
        contract.functions.transfer(to, amount_wei)
        .with_owner(from_address)
        .fee_limit(settings.TRC20_TRANSFER_FEE_LIMIT_SUN)
        .build()
        .sign(key)
    )
    result = txn.broadcast()
    return result.get("txid") or result.get("id") or str(result)


async def get_or_create_sweep_record(
    session: Any, deposit: Deposit, wallet: WalletAddress
) -> Trc20Sweep:
    from sqlalchemy import select

    existing = (
        await session.execute(select(Trc20Sweep).where(Trc20Sweep.deposit_id == deposit.id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    record = Trc20Sweep(
        deposit_id=deposit.id,
        derived_address=wallet.address,
        derivation_index=wallet.derivation_index or 0,
        treasury_address=settings.TRC_TREASURY_ADDRESS,
        gross_amount_usd=deposit.gross_amount_usd,
        status="pending",
    )
    session.add(record)
    await session.flush()
    await session.refresh(record)
    return record


async def sweep_trc20_deposit(
    session: Any,
    deposit: Deposit,
    wallet: WalletAddress,
) -> Trc20Sweep:
    """Consolidate one confirmed TRC20 USDT deposit to the treasury.

    Steps:
        1. Derive the private key for the deposit address.
        2. Check USDT balance on-chain.
        3. If the address lacks TRX for the transfer fee, top it up from the
           gas wallet (fixed amount — TRC20 fee estimation via energy/
           bandwidth is not modeled here, unlike BSC's gas price).
        4. Transfer all USDT to the treasury address.
        5. Return any leftover TRX dust to the gas wallet.
    """
    _assert_configured()
    if not settings.ENABLE_TRC20_SWEEP:
        raise ConfigurationError("TRC20 sweep is disabled via ENABLE_TRC20_SWEEP.")

    record = await get_or_create_sweep_record(session, deposit, wallet)
    if record.status in ("swept", "in_progress"):
        return record

    record.status = "in_progress"
    await session.flush()

    try:
        index = wallet.derivation_index
        if index is None:
            raise ValueError("WalletAddress has no derivation_index for TRC20 sweep.")

        private_key, derived_address = _derive_tron_keypair(settings.ACCOUNT_XPRV_TRC20, index)
        if derived_address != wallet.address:
            raise ConfigurationError(
                f"Derived address {derived_address} does not match stored address {wallet.address}."
            )

        client = _tron_client()
        usdt_balance = _usdt_balance(client, derived_address)
        if usdt_balance <= 0:
            raise ValueError(f"No USDT balance to sweep on {derived_address}.")

        record.gross_amount_usd = usdt_balance
        record.swept_amount_usd = usdt_balance
        await session.flush()

        # Step 1: gas (TRX) top-up if needed.
        trx_balance = _trx_balance(client, derived_address)
        if trx_balance < settings.TRC20_GAS_MIN_TRX:
            topup = settings.TRC20_GAS_TOPUP_TRX
            tx_hash = _send_trx(client, settings.TRC_GAS_WALLET_PRIVATE_KEY, derived_address, topup)
            record.gas_topup_tx_hash = tx_hash
            record.gas_topup_amount_trx = topup
            logger.info(
                "trc20.gas_topup deposit=%s address=%s amount=%s tx=%s",
                deposit.id,
                derived_address,
                topup,
                tx_hash,
            )

        # Step 2: sweep USDT.
        amount_wei = int(usdt_balance * USDT_DECIMALS)
        sweep_tx = _sweep_usdt(client, private_key, derived_address, settings.TRC_TREASURY_ADDRESS, amount_wei)
        record.sweep_tx_hash = sweep_tx
        logger.info(
            "trc20.sweep deposit=%s address=%s amount=%s tx=%s",
            deposit.id,
            derived_address,
            usdt_balance,
            sweep_tx,
        )

        # Step 3: return dust TRX to gas wallet.
        leftover_trx = _trx_balance(client, derived_address)
        if leftover_trx > settings.TRC20_GAS_DUST_TRX:
            return_amount = leftover_trx - settings.TRC20_GAS_DUST_TRX
            gas_wallet_address = _gas_wallet_address(client)
            private_key_hex = private_key.hex()
            return_tx = _send_trx(client, private_key_hex, gas_wallet_address, return_amount)
            record.dust_return_tx_hash = return_tx
            record.dust_return_amount_trx = str(return_amount)
            logger.info(
                "trc20.dust_return deposit=%s address=%s amount=%s tx=%s",
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
        logger.exception("trc20.sweep_failed deposit=%s error=%s", deposit.id, exc)

    await session.flush()
    await session.refresh(record)
    return record
