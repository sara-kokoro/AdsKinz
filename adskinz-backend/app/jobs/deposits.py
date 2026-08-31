"""Watch-only USDT deposit polling for TON, TRC20 and BNB Smart Chain."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

import httpx
from sqlalchemy import select

from app.config import settings
from app.core.enums import DepositStatus
from app.core.errors import NotFoundError, ValidationError
from app.database import session_scope
from app.models.accounts import Advertiser
from app.models.finance import Deposit, WalletAddress
from app.services import bep20_sweep_service, billing_service, email_service, trc20_sweep_service, wallet_service

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


def _normalise_ton_address(value: Any) -> str:
    """Canonicalise a TON address to raw ``wc:hex`` form for comparison.

    TonAPI's ``/v2/accounts/{id}/events`` returns jetton sender/recipient
    and jetton-master addresses in raw form (e.g. ``0:9311f832e4ca...``),
    while our own config and derived wallet addresses are stored in
    user-friendly form (e.g. ``UQCT...``). A plain string compare between
    the two never matches, which was silently dropping every TON deposit
    regardless of memo/amount. Route both sides through this first.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        from pytoniq_core import Address  # local import: only needed for TON

        return Address(text).to_str(is_user_friendly=False).lower()
    except Exception:
        # Fall back to a plain compare rather than crash the poller if the
        # address is malformed or the library can't parse it.
        return text.lower()


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


async def _bnb_latest_block(client: httpx.AsyncClient) -> int:
    """BSCTrace/MegaNode speaks standard JSON-RPC 2.0 (POST), not BscScan's
    REST module/action GET style. ``eth_blockNumber`` is unchanged from the
    old proxy call — only the transport and response shape differ."""
    response = await client.post(
        settings.MEGANODE_BSC_RPC_URL,
        json={"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []},
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(str(payload["error"]))
    latest_raw = payload.get("result")
    return int(latest_raw, 16) if isinstance(latest_raw, str) else 0


async def _bnb_transfers(client: httpx.AsyncClient, address: str, latest_block: int) -> list[ChainTransfer]:
    """BSCTrace/MegaNode equivalent of BscScan's ``tokentx``: the enhanced
    ``nr_getAssetTransfers`` RPC method, filtered server-side to ERC20
    ("20") transfers landing on our address from the USDT BEP20 contract."""
    response = await client.post(
        settings.MEGANODE_BSC_RPC_URL,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "nr_getAssetTransfers",
            "params": [
                {
                    "category": ["20"],
                    "contractAddresses": [settings.USDT_BEP20_CONTRACT],
                    "toAddress": address,
                    "order": "desc",
                    "maxCount": "0x3E8",
                }
            ],
        },
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        error = payload["error"]
        message = error.get("message") if isinstance(error, dict) else error
        raise RuntimeError(str(message or "MegaNode/BSCTrace rejected the request."))

    result = payload.get("result") or {}
    transfers: list[ChainTransfer] = []
    for item in result.get("transfers", []):
        if _normalise_address(item.get("to")) != _normalise_address(address):
            continue
        if _normalise_address(item.get("contractAddress")) != _normalise_address(
            settings.USDT_BEP20_CONTRACT
        ):
            continue
        raw_value = item.get("value")
        raw_decimal = item.get("decimal")
        decimals = int(raw_decimal, 16) if isinstance(raw_decimal, str) else 18
        amount = (
            _decimal_amount(int(raw_value, 16), decimals)
            if isinstance(raw_value, str)
            else None
        )
        tx_hash = str(item.get("hash") or "")
        if amount is None or amount <= 0 or not tx_hash:
            continue
        raw_block = item.get("blockNum")
        block_number = int(raw_block, 16) if isinstance(raw_block, str) else None
        confirmations = (
            max(0, latest_block - block_number + 1)
            if block_number is not None and latest_block
            else 0
        )
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
    """Read inbound USDT jetton transfers for one account from TonAPI.

    Uses GET /v2/accounts/{account_id}/events, the only TonAPI endpoint that
    exposes a decoded ``comment`` field for jetton transfers (confirmed
    against TonAPI's own OpenAPI spec — the jettons/history endpoint only
    has a free-form, unstructured ``payload`` and cannot be used to match a
    memo reliably). Each event's actions are scanned for a JettonTransfer
    whose jetton is our USDT master and whose recipient is this address.
    """
    headers = {"Authorization": f"Bearer {settings.TONAPI_API_KEY}"} if settings.TONAPI_API_KEY else {}
    response = await client.get(
        f"{settings.TONAPI_BASE_URL.rstrip('/')}/v2/accounts/{address}/events",
        params={"limit": 100, "subject_only": "true"},
        headers=headers,
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError(str(payload["error"]))

    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        events = []

    transfers: list[ChainTransfer] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_id = event.get("event_id")
        for action in event.get("actions") or []:
            if not isinstance(action, dict) or action.get("type") != "JettonTransfer":
                continue
            details = action.get("JettonTransfer")
            if not isinstance(details, dict):
                continue

            jetton = details.get("jetton") or {}
            jetton_master = jetton.get("address") if isinstance(jetton, dict) else None
            if _normalise_ton_address(jetton_master) != _normalise_ton_address(
                settings.USDT_TON_JETTON_MASTER
            ):
                continue

            recipient = details.get("recipient") or {}
            recipient_address = recipient.get("address") if isinstance(recipient, dict) else None
            if _normalise_ton_address(recipient_address) != _normalise_ton_address(address):
                continue

            amount = _decimal_amount(details.get("amount"), (jetton or {}).get("decimals", 6))
            comment = details.get("comment")
            memo = comment.strip() if isinstance(comment, str) and comment.strip() else None
            base_tx = action.get("base_transactions") or []
            tx_hash = str(base_tx[0]) if base_tx else str(event_id or "")

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
) -> tuple[list[ChainTransfer], list[str]]:
    """Returns ``(transfers, errors)``. ``errors`` holds a short reason per
    address that failed (bad API key, rate limit, RPC down, ...) instead of
    silently collapsing every failure into an empty result — a caller like
    the on-demand "Verify" button needs to tell "nothing found yet" apart
    from "the scan itself couldn't run"."""
    unique_addresses = {row.address for row in addresses}
    transfers: list[ChainTransfer] = []
    errors: list[str] = []
    if network == "ton":
        for address in unique_addresses:
            try:
                transfers.extend(await _ton_transfers(client, address))
            except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                logger.warning("deposits.ton_address_poll_failed address=%s error=%s", address, exc)
                errors.append(str(exc))
    elif network == "trc20":
        for address in unique_addresses:
            try:
                transfers.extend(await _trc20_transfers(client, address))
            except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                logger.warning("deposits.trc20_address_poll_failed address=%s error=%s", address, exc)
                errors.append(str(exc))
    elif network == "bnb":
        try:
            latest_block = await _bnb_latest_block(client)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            logger.warning("deposits.bnb_latest_block_failed error=%s", exc)
            return transfers, [str(exc)]
        for i, address in enumerate(unique_addresses):
            if i > 0:
                await asyncio.sleep(0.25)  # stay under MegaNode's free-tier rate limit
            try:
                transfers.extend(await _bnb_transfers(client, address, latest_block))
            except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                # One noisy/rate-limited address must not blind the scan to
                # every other advertiser's deposits in this run.
                logger.warning("deposits.bnb_address_poll_failed address=%s error=%s", address, exc)
                errors.append(str(exc))
    return transfers, errors


def _required_confirmations(network: str) -> int:
    return {
        "ton": settings.DEPOSIT_MIN_CONFIRMATIONS_TON,
        "trc20": settings.DEPOSIT_MIN_CONFIRMATIONS_TRC20,
        "bnb": settings.DEPOSIT_MIN_CONFIRMATIONS_BEP20,
    }[network]


async def _process_transfers(
    session: Any,
    discovered: list[ChainTransfer],
    address_index: dict[tuple[str, str, str], WalletAddress],
    now: datetime,
    summary: dict[str, int],
    notifications: list[tuple[str, Decimal, str, Decimal]],
) -> None:
    """Persist discovered transfers, credit confirmed ones, and trigger sweeps.

    Shared by the scheduled batch watcher and the on-demand single-address
    verify endpoint — the two must never diverge in how a deposit is
    validated and credited.
    """
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
                logger.warning("deposits.bep20_sweep_failed deposit=%s error=%s", deposit.id, exc)

        # Automatic TRC20 sweep: send USDT from the derived address to treasury.
        if deposit.network == "trc20" and wallet.derivation_index is not None:
            try:
                await trc20_sweep_service.sweep_trc20_deposit(session, deposit, wallet)
            except Exception as exc:
                logger.warning("deposits.trc20_sweep_failed deposit=%s error=%s", deposit.id, exc)

        notifications.append(
            (advertiser.email, Decimal(deposit.amount_usd or 0), deposit.network, deposit.fee_usd)
        )


async def ton_webhook_trigger() -> dict:
    """Scan only TON wallets — called when TonAPI's webhook notifies us that
    something happened on the hot wallet, instead of waiting for the next
    scheduled cycle. Scoped to TON only so a burst of TON notifications never
    burns TronGrid/MegaNode rate limit budget."""
    summary = {"transfers_seen": 0, "deposits_created": 0, "deposits_confirmed": 0, "deposits_credited": 0}
    notifications: list[tuple[str, Decimal, str, Decimal]] = []
    now = datetime.now(UTC)

    async with session_scope() as session:
        addresses = (
            (await session.execute(select(WalletAddress).where(WalletAddress.network == "ton")))
            .scalars()
            .all()
        )
        if not addresses:
            return summary

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
                discovered, _errors = await _network_transfers(client, "ton", addresses)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            logger.warning("deposits.ton_webhook_poll_failed error=%s", exc)
            return summary

        for row in addresses:
            row.last_scanned_at = now
        address_index = {
            ("ton", _normalise_address(row.address), (row.memo or "").lower()): row for row in addresses
        }
        await _process_transfers(session, discovered, address_index, now, summary, notifications)

    for email, amount, net, fee in notifications:
        await email_service.send_deposit_confirmed(email, amount=amount, network=net, fee=fee)
    return summary


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
                    transfers, network_errors = await _network_transfers(client, network, rows)
                    discovered.extend(transfers)
                    if network_errors:
                        summary["network_errors"] += len(network_errors)
                except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                    summary["network_errors"] += 1
                    logger.warning("deposits.network_poll_failed network=%s error=%s", network, exc)

        for row in addresses:
            row.last_scanned_at = now

        address_index = {
            (row.network, _normalise_address(row.address), (row.memo or "").lower()): row
            for row in addresses
        }
        await _process_transfers(session, discovered, address_index, now, summary, notifications)

    for email, amount, network, fee in notifications:
        await email_service.send_deposit_confirmed(email, amount=amount, network=network, fee=fee)
    return summary


async def verify_deposit_address(advertiser_id: uuid.UUID, network: str) -> dict:
    """On-demand check for one advertiser's own deposit address, right now —
    instead of waiting up to one scheduler cycle. Same credit/sweep path as
    the batch watcher, scoped to a single wallet so it stays fast and cheap
    enough to call directly from a "Verify" button."""
    if network not in ("ton", "trc20", "bnb"):
        raise ValidationError(f"Unknown network '{network}'.")

    summary = {"transfers_seen": 0, "deposits_created": 0, "deposits_confirmed": 0, "deposits_credited": 0}
    notifications: list[tuple[str, Decimal, str, Decimal]] = []
    now = datetime.now(UTC)

    async with session_scope() as session:
        wallet = (
            await session.execute(
                select(WalletAddress).where(
                    WalletAddress.advertiser_id == advertiser_id,
                    WalletAddress.network == network,
                )
            )
        ).scalar_one_or_none()
        if wallet is None:
            raise NotFoundError(f"No {network} deposit address on file for this account.")

        discovered: list[ChainTransfer] = []
        scan_errors: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
                discovered, scan_errors = await _network_transfers(client, network, [wallet])
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            logger.warning(
                "deposits.verify_poll_failed advertiser=%s network=%s error=%s",
                advertiser_id, network, exc,
            )
            scan_errors = [str(exc)]

        wallet.last_scanned_at = now
        address_index = {(network, _normalise_address(wallet.address), (wallet.memo or "").lower()): wallet}
        await _process_transfers(session, discovered, address_index, now, summary, notifications)

    if scan_errors:
        # Surfaced to the "Verify" button so a broken scan (bad API key,
        # provider down, rate limit) reads as exactly that instead of a
        # silent "nothing found" that looks identical to a deposit that
        # simply hasn't arrived yet.
        summary["scan_error"] = scan_errors[0]

    for email, amount, net, fee in notifications:
        await email_service.send_deposit_confirmed(email, amount=amount, network=net, fee=fee)
    return summary
