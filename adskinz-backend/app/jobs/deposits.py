"""Watch-only USDT deposit polling for TON, TRC20 and BNB Smart Chain."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

import httpx
from sqlalchemy import select

from app.config import settings
from app.core.enums import DepositStatus
from app.database import session_scope
from app.models.accounts import Advertiser
from app.models.finance import Deposit, WalletAddress
from app.services import bep20_sweep_service, billing_service, email_service, wallet_service

logger = logging.getLogger(__name__)

HTTP_TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True, slots=True)
class ChainTransfer:
    """Normalised incoming USDT transfer returned by a network explorer."""

    network: str
    tx_hash: str
    address: str
    gross_amount: Decimal
    confirmations: int
    block_number: int | None = None
    memo: str | None = None


def _decimal_amount(raw: Any, decimals: Any) -> Decimal | None:
    try:
        return Decimal(str(raw)) / (Decimal(10) ** int(decimals))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _normalise_address(value: Any) -> str:
    return str(value or "").strip().lower()


def _extract_strings(value: Any, names: set[str]) -> list[str]:
    """Collect named scalar values from inconsistent explorer payload shapes."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in names and isinstance(child, (str, int, float)):
                found.append(str(child))
            found.extend(_extract_strings(child, names))
    elif isinstance(value, list):
        for child in value:
            found.extend(_extract_strings(child, names))
    return found


async def _trc20_transfers(client: httpx.AsyncClient, address: str) -> list[ChainTransfer]:
    headers = {"TRON-PRO-API-KEY": settings.TRONGRID_API_KEY} if settings.TRONGRID_API_KEY else {}
    latest_response = await client.get(
        f"{settings.TRONGRID_BASE_URL.rstrip('/')}/wallet/getnowblock",
        headers=headers,
    )
    latest_response.raise_for_status()
    latest_block = int(
        (latest_response.json().get("block_header") or {}).get("raw_data", {}).get("number", 0)
    )
    response = await client.get(
        f"{settings.TRONGRID_BASE_URL.rstrip('/')}/v1/accounts/{address}/transactions/trc20",
        params={
            "only_confirmed": "true",
            "only_to": "true",
            "contract_address": settings.USDT_TRC20_CONTRACT,
            "limit": 200,
        },
        headers=headers,
    )
    response.raise_for_status()
    transfers: list[ChainTransfer] = []
    for item in response.json().get("data", []):
        if _normalise_address(item.get("to")) != _normalise_address(address):
            continue
        token = item.get("token_info") or {}
        if _normalise_address(token.get("address")) != _normalise_address(
            settings.USDT_TRC20_CONTRACT
        ):
            continue
        amount = _decimal_amount(item.get("value"), token.get("decimals", 6))
        tx_hash = str(item.get("transaction_id") or item.get("txID") or "")
        if amount is None or amount <= 0 or not tx_hash:
            continue
        raw_block_number = item.get("block_number", item.get("blockNumber"))
        block_number = int(raw_block_number) if str(raw_block_number).isdigit() else None
        confirmations = (
            max(0, latest_block - block_number + 1)
            if block_number is not None and latest_block
            else 0
        )
        transfers.append(
            ChainTransfer(
                network="trc20",
                tx_hash=tx_hash,
                address=address,
                gross_amount=amount,
                confirmations=confirmations,
                block_number=block_number,
            )
        )
    return transfers


async def _bnb_transfers(client: httpx.AsyncClient, address: str) -> list[ChainTransfer]:
    latest_response = await client.get(
        settings.BSCSCAN_BASE_URL,
        params={"module": "proxy", "action": "eth_blockNumber", "apikey": settings.BSCSCAN_API_KEY},
    )
    latest_response.raise_for_status()
    latest_raw = latest_response.json().get("result")
    latest_block = int(str(latest_raw), 16) if isinstance(latest_raw, str) else 0

    response = await client.get(
        settings.BSCSCAN_BASE_URL,
        params={
            "module": "account",
            "action": "tokentx",
            "contractaddress": settings.USDT_BEP20_CONTRACT,
            "address": address,
            "page": 1,
            "offset": 200,
            "sort": "desc",
            "apikey": settings.BSCSCAN_API_KEY,
        },
    )
    response.raise_for_status()
    payload = response.json()
    if str(payload.get("status", "1")) not in {"1", "true", "True"}:
        message = payload.get("result") or payload.get("message") or "BscScan rejected the request."
        raise RuntimeError(str(message))

    transfers: list[ChainTransfer] = []
    for item in payload.get("result", []):
        if _normalise_address(item.get("to")) != _normalise_address(address):
            continue
        if _normalise_address(item.get("contractAddress")) != _normalise_address(
            settings.USDT_BEP20_CONTRACT
        ):
            continue
        amount = _decimal_amount(item.get("value"), item.get("tokenDecimal", 18))
        tx_hash = str(item.get("hash") or "")
        if amount is None or amount <= 0 or not tx_hash:
            continue
        block_number = (
            int(item["blockNumber"]) if str(item.get("blockNumber", "")).isdigit() else None
        )
        confirmations = int(item.get("confirmations") or 0)
        if not confirmations and block_number is not None and latest_block:
            confirmations = max(0, latest_block - block_number + 1)
        transfers.append(
            ChainTransfer(
                network="bnb",
                tx_hash=tx_hash,
                address=address,
                gross_amount=amount,
                confirmations=confirmations,
                block_number=block_number,
            )
        )
    return transfers


async def _ton_transfers(client: httpx.AsyncClient, address: str) -> list[ChainTransfer]:
    """Read decoded inbound USDT jetton notifications from Toncenter.

    Toncenter versions expose decoded fields under slightly different names, so
    this accepts the documented v2 message shape as well as common decoded
    variants. Transfers without both a USDT master and the advertiser memo are
    deliberately ignored rather than risking a credit for native TON.
    """
    headers = {"X-API-Key": settings.TONCENTER_API_KEY} if settings.TONCENTER_API_KEY else {}
    response = await client.get(
        f"{settings.TONCENTER_BASE_URL.rstrip('/')}/getTransactions",
        params={"address": address, "limit": 200, "archival": "true"},
        headers=headers,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok", True):
        raise RuntimeError(str(payload.get("error") or "Toncenter rejected the request."))

    transfers: list[ChainTransfer] = []
    for transaction in payload.get("result", []):
        masters = _extract_strings(
            transaction,
            {"jetton_master", "jetton_master_address", "master_address"},
        )
        if not any(
            _normalise_address(value) == _normalise_address(settings.USDT_TON_JETTON_MASTER)
            for value in masters
        ):
            continue
        operation_names = _extract_strings(transaction, {"decoded_op_name", "operation", "op_name"})
        if operation_names and not any("jetton" in value.lower() for value in operation_names):
            continue
        amount_values = _extract_strings(transaction, {"amount", "jetton_amount"})
        memo_values = _extract_strings(transaction, {"comment", "memo", "text"})
        hash_values = _extract_strings(transaction, {"hash"})
        amount = _decimal_amount(amount_values[0], 6) if amount_values else None
        tx_hash = hash_values[0] if hash_values else ""
        memo = next((value for value in memo_values if value.strip()), None)
        if amount is None or amount <= 0 or not tx_hash or not memo:
            continue
        transfers.append(
            ChainTransfer(
                network="ton",
                tx_hash=tx_hash,
                address=address,
                memo=memo,
                gross_amount=amount,
                confirmations=settings.DEPOSIT_MIN_CONFIRMATIONS_TON,
            )
        )
    return transfers


async def _network_transfers(
    client: httpx.AsyncClient, network: str, addresses: Iterable[WalletAddress]
) -> list[ChainTransfer]:
    unique_addresses = {row.address for row in addresses}
    transfers: list[ChainTransfer] = []
    if network == "ton":
        for address in unique_addresses:
            transfers.extend(await _ton_transfers(client, address))
    elif network == "trc20":
        for address in unique_addresses:
            transfers.extend(await _trc20_transfers(client, address))
    elif network == "bnb":
        for address in unique_addresses:
            transfers.extend(await _bnb_transfers(client, address))
    return transfers


def _required_confirmations(network: str) -> int:
    return {
        "ton": settings.DEPOSIT_MIN_CONFIRMATIONS_TON,
        "trc20": settings.DEPOSIT_MIN_CONFIRMATIONS_TRC20,
        "bnb": settings.DEPOSIT_MIN_CONFIRMATIONS_BEP20,
    }[network]


async def deposit_watcher() -> dict:
    """Discover watch-only USDT deposits, persist them, then credit safely."""
    summary = {
        "wallet_addresses": 0,
        "transfers_seen": 0,
        "deposits_created": 0,
        "deposits_confirmed": 0,
        "deposits_credited": 0,
        "network_errors": 0,
    }
    notifications: list[tuple[str, Decimal, str, Decimal]] = []
    now = datetime.now(UTC)

    async with session_scope() as session:
        addresses = (await session.execute(select(WalletAddress))).scalars().all()
        summary["wallet_addresses"] = len(addresses)
        by_network: dict[str, list[WalletAddress]] = {"ton": [], "trc20": [], "bnb": []}
        for row in addresses:
            if row.network in by_network:
                by_network[row.network].append(row)

        discovered: list[ChainTransfer] = []
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            for network, rows in by_network.items():
                if not rows:
                    continue
                try:
                    discovered.extend(await _network_transfers(client, network, rows))
                except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                    summary["network_errors"] += 1
                    logger.warning("deposits.network_poll_failed network=%s error=%s", network, exc)

        for row in addresses:
            row.last_scanned_at = now

        address_index = {
            (row.network, _normalise_address(row.address), (row.memo or "").lower()): row
            for row in addresses
        }
        for transfer in discovered:
            memo_key = (transfer.memo or "").strip().lower() if transfer.network == "ton" else ""
            wallet = address_index.get(
                (transfer.network, _normalise_address(transfer.address), memo_key)
            )
            if wallet is None:
                continue
            summary["transfers_seen"] += 1

            deposit = (
                await session.execute(select(Deposit).where(Deposit.tx_hash == transfer.tx_hash))
            ).scalar_one_or_none()
            if deposit is None:
                net_amount, fee = wallet_service.net_credited_amount(
                    transfer.network, transfer.gross_amount
                )
                deposit = Deposit(
                    advertiser_id=wallet.advertiser_id,
                    network=transfer.network,
                    derived_address=wallet.address,
                    memo=wallet.memo if transfer.network == "ton" else None,
                    gross_amount_usd=transfer.gross_amount,
                    fee_usd=fee,
                    amount_usd=net_amount,
                    tx_hash=transfer.tx_hash,
                    block_number=transfer.block_number,
                    confirmations=transfer.confirmations,
                )
                session.add(deposit)
                await session.flush()
                summary["deposits_created"] += 1
            else:
                deposit.confirmations = max(deposit.confirmations, transfer.confirmations)
                if transfer.block_number is not None:
                    deposit.block_number = transfer.block_number

            if (
                deposit.confirmations < _required_confirmations(deposit.network)
                or deposit.credited
            ):
                continue

            advertiser = await session.get(Advertiser, deposit.advertiser_id, with_for_update=True)
            if advertiser is None:
                logger.error("deposits.advertiser_missing deposit=%s", deposit.id)
                continue
            credited = await billing_service.credit_deposit(
                session,
                advertiser=advertiser,
                net_amount=Decimal(deposit.amount_usd or 0),
                reference_id=deposit.id,
                network=deposit.network,
            )
            deposit.status = DepositStatus.CONFIRMED.value
            deposit.confirmed_at = now
            deposit.credited = True
            summary["deposits_confirmed"] += 1
            if credited > 0:
                summary["deposits_credited"] += 1

            # Automatic BEP20 sweep: send USDT from the derived address to treasury.
            if deposit.network == "bnb" and wallet.derivation_index is not None:
                try:
                    await bep20_sweep_service.sweep_bep20_deposit(session, deposit, wallet)
                except Exception as exc:
                    logger.warning(
                        "deposits.bep20_sweep_failed deposit=%s error=%s",
                        deposit.id,
                        exc,
                    )

            notifications.append(
                (
                    advertiser.email,
                    Decimal(deposit.amount_usd or 0),
                    deposit.network,
                    deposit.fee_usd,
                )
            )

    for email, amount, network, fee in notifications:
        await email_service.send_deposit_confirmed(email, amount=amount, network=network, fee=fee)
    return summary
