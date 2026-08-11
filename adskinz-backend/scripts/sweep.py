"""
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! WARNING !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
THIS IS A STANDALONE, MANUAL OPERATOR TOOL. IT IS NEVER DEPLOYED AND MUST NEVER
BE IMPORTED BY THE ADSKINZ SERVICE. THE DOCKER IMAGE EXCLUDES `scripts/`.

It is deliberately not an automatic sweeping mechanism. The mnemonic is accepted
only through the terminal's hidden interactive prompt; it is never read from an
environment variable or file, logged, persisted, or sent to an API. Review each
derived address, token balance, destination, network fee, and confirmation text
before allowing any transaction to be broadcast.

Use this only from a trusted local machine with a manually supplied mnemonic and
the required provider credentials. A transaction is broadcast only after the
operator types the exact confirmation requested for that one source address.
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from getpass import getpass

import httpx
from bip_utils import Bip39MnemonicValidator, Bip39SeedGenerator, Bip44, Bip44Changes, Bip44Coins
from eth_account import Account
from eth_utils import is_address, to_checksum_address
from tronpy import Tron
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider

from app.config import settings

USDT_DECIMALS = Decimal("1000000")
DEFAULT_BSC_RPC_URL = "https://bsc-dataseed.binance.org/"


@dataclass(frozen=True)
class DerivedWallet:
    """Ephemeral key material held only for this single process invocation."""

    index: int
    trc20_address: str
    trc20_private_key: bytes
    bsc_address: str
    bsc_private_key: bytes


def derive_wallet(mnemonic: str, index: int) -> DerivedWallet:
    """Derive m/44'/195'/0'/0/i and m/44'/60'/0'/0/i from an in-memory mnemonic."""
    seed = Bip39SeedGenerator(mnemonic).Generate()
    tron_context = (
        Bip44.FromSeed(seed, Bip44Coins.TRON)
        .Purpose()
        .Coin()
        .Account(0)
        .Change(Bip44Changes.CHAIN_EXT)
        .AddressIndex(index)
    )
    bsc_context = (
        Bip44.FromSeed(seed, Bip44Coins.ETHEREUM)
        .Purpose()
        .Coin()
        .Account(0)
        .Change(Bip44Changes.CHAIN_EXT)
        .AddressIndex(index)
    )
    bsc_private_key = bsc_context.PrivateKey().Raw().ToBytes()
    return DerivedWallet(
        index=index,
        trc20_address=tron_context.PublicKey().ToAddress(),
        trc20_private_key=tron_context.PrivateKey().Raw().ToBytes(),
        bsc_address=Account.from_key(bsc_private_key).address,
        bsc_private_key=bsc_private_key,
    )


def tron_client() -> Tron:
    """Create a local client for read calls and a later explicitly confirmed send."""
    if not settings.TRONGRID_API_KEY:
        raise RuntimeError("TRONGRID_API_KEY is required for TRC20 balance checks.")
    provider = HTTPProvider(
        endpoint_uri=settings.TRONGRID_BASE_URL,
        api_key=settings.TRONGRID_API_KEY,
    )
    return Tron(provider=provider)


def trc20_balance(client: Tron, address: str) -> int:
    contract = client.get_contract(settings.USDT_TRC20_CONTRACT)
    return int(contract.functions.balanceOf(address))


def bscscan_balance(address: str) -> int:
    """Read the USDT balance via BscScan; this performs no signing or sending."""
    if not settings.BSCSCAN_API_KEY:
        raise RuntimeError("BSCSCAN_API_KEY is required for BEP20 balance checks.")
    response = httpx.get(
        settings.BSCSCAN_BASE_URL,
        params={
            "module": "account",
            "action": "tokenbalance",
            "contractaddress": settings.USDT_BEP20_CONTRACT,
            "address": address,
            "tag": "latest",
            "apikey": settings.BSCSCAN_API_KEY,
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "1":
        raise RuntimeError(payload.get("result") or payload.get("message") or "BscScan request failed.")
    return int(payload["result"])


def rpc_call(rpc_url: str, method: str, params: list[object]) -> object:
    """Call a BSC JSON-RPC method without retaining any request data."""
    response = httpx.post(
        rpc_url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"{method}: {payload['error']}")
    return payload["result"]


def bsc_transfer_data(destination: str, amount: int) -> str:
    """Encode ERC-20 transfer(address,uint256) without a service dependency."""
    destination_hex = destination.removeprefix("0x").lower()
    return "0xa9059cbb" + destination_hex.rjust(64, "0") + format(amount, "064x")


def broadcast_trc20(
    client: Tron,
    source: DerivedWallet,
    destination: str,
    amount: int,
) -> object:
    """Broadcast one already-confirmed TRC20 USDT transfer."""
    contract = client.get_contract(settings.USDT_TRC20_CONTRACT)
    transaction = (
        contract.functions.transfer(destination, amount)
        .with_owner(source.trc20_address)
        .fee_limit(100_000_000)
        .build()
        .sign(PrivateKey(source.trc20_private_key))
    )
    return transaction.broadcast()


def broadcast_bsc(
    rpc_url: str,
    source: DerivedWallet,
    destination: str,
    amount: int,
) -> object:
    """Broadcast one already-confirmed BEP20 USDT transfer using the local key."""
    data = bsc_transfer_data(destination, amount)
    nonce = int(str(rpc_call(rpc_url, "eth_getTransactionCount", [source.bsc_address, "pending"])), 16)
    gas_price = int(str(rpc_call(rpc_url, "eth_gasPrice", [])), 16)
    contract = to_checksum_address(settings.USDT_BEP20_CONTRACT)
    estimate = rpc_call(
        rpc_url,
        "eth_estimateGas",
        [{"from": source.bsc_address, "to": contract, "value": "0x0", "data": data}],
    )
    chain_id = int(str(rpc_call(rpc_url, "eth_chainId", [])), 16)
    transaction = {
        "chainId": chain_id,
        "nonce": nonce,
        "to": contract,
        "value": 0,
        "gas": int(str(estimate), 16),
        "gasPrice": gas_price,
        "data": data,
    }
    signed = Account.sign_transaction(transaction, source.bsc_private_key)
    return rpc_call(rpc_url, "eth_sendRawTransaction", [signed.raw_transaction.hex()])


def display_usdt(amount: int) -> str:
    return f"{Decimal(amount) / USDT_DECIMALS:.6f} USDT"


def require_confirmation(network: str, source_address: str) -> bool:
    expected = f"SWEEP {network} {source_address}"
    print(f"\nTo broadcast this one transaction, type exactly: {expected}")
    return input("> ").strip() == expected


def main() -> None:
    print(__doc__)
    mnemonic = getpass("Mnemonic (hidden, read once, never stored): ").strip()
    try:
        Bip39MnemonicValidator().Validate(mnemonic)
    except ValueError as exc:
        raise SystemExit(f"Invalid BIP-39 mnemonic: {exc}") from exc

    try:
        count = int(input("Number of derivation indexes to inspect, starting at 0 [1]: ") or "1")
    except ValueError as exc:
        raise SystemExit("The derivation index count must be an integer.") from exc
    if not 1 <= count <= 100:
        raise SystemExit("Choose between 1 and 100 addresses for this manual run.")

    trc20_destination = input("TRC20 consolidation destination (blank skips TRC20): ").strip()
    bsc_destination = input("BSC consolidation destination (blank skips BSC): ").strip()
    bsc_rpc_url = input(f"BSC RPC URL [{DEFAULT_BSC_RPC_URL}]: ").strip() or DEFAULT_BSC_RPC_URL

    if bsc_destination and not is_address(bsc_destination):
        raise SystemExit("The BSC destination is not a valid EVM address.")
    if bsc_destination:
        bsc_destination = to_checksum_address(bsc_destination)

    client = tron_client()
    wallets = [derive_wallet(mnemonic, index) for index in range(count)]
    del mnemonic

    for wallet in wallets:
        print(f"\nIndex {wallet.index}")
        try:
            trc20_amount = trc20_balance(client, wallet.trc20_address)
            print(f"  TRC20 {wallet.trc20_address}: {display_usdt(trc20_amount)}")
        except Exception as exc:
            trc20_amount = 0
            print(f"  TRC20 {wallet.trc20_address}: balance lookup failed ({exc})")

        try:
            bsc_amount = bscscan_balance(wallet.bsc_address)
            print(f"  BSC   {wallet.bsc_address}: {display_usdt(bsc_amount)}")
        except Exception as exc:
            bsc_amount = 0
            print(f"  BSC   {wallet.bsc_address}: balance lookup failed ({exc})")

        if trc20_amount and trc20_destination:
            if require_confirmation("TRC20", wallet.trc20_address):
                result = broadcast_trc20(client, wallet, trc20_destination, trc20_amount)
                print(f"  TRC20 broadcast submitted: {result}")
            else:
                print("  TRC20 broadcast cancelled.")

        if bsc_amount and bsc_destination:
            if require_confirmation("BSC", wallet.bsc_address):
                result = broadcast_bsc(bsc_rpc_url, wallet, bsc_destination, bsc_amount)
                print(f"  BSC broadcast submitted: {result}")
            else:
                print("  BSC broadcast cancelled.")


if __name__ == "__main__":
    main()
