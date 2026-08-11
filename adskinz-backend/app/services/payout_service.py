"""Outgoing USDT payouts on TON, from the dedicated payout wallet only.

Wallet separation is intentional and must never be relaxed:

* **Wallet 1** receives advertiser deposits on derived addresses. The service
  only ever holds its extended *public* key. Nothing here can spend from it,
  and consolidating those funds is a manual, local, operator-run script.
* **Wallet 2** is a separate hot wallet funded deliberately by the operator.
  Its private key (``WALLET_2_PRIVATE_KEY``) signs publisher payouts and
  nothing else.

When ``ENABLE_AUTO_PAYOUT`` is off, this module signs nothing: an approved
withdrawal simply waits for the operator to send it manually and record the
transaction hash.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    return bool(settings.ENABLE_AUTO_PAYOUT and settings.WALLET_2_PRIVATE_KEY)


async def send_payout(
    *, address: str, amount: Decimal, memo: str
) -> tuple[str | None, str | None]:
    """Send ``amount`` USDT to ``address`` on TON with ``memo`` as the comment.

    Returns ``(tx_hash, error)``. Exactly one of the two is set.
    """
    if not is_enabled():
        return None, (
            "Automatic payouts are disabled on this instance. Send the transfer "
            "manually from the payout wallet and record the transaction hash."
        )

    try:
        return await _send_ton_jetton(address=address, amount=amount, memo=memo)
    except httpx.HTTPError as exc:
        logger.exception("payout.network_error address=%s", address)
        return None, f"Network error while broadcasting the payout: {exc}"
    except Exception as exc:  # noqa: BLE001 - never let a payout crash the request
        logger.exception("payout.failed address=%s", address)
        return None, str(exc)


async def _send_ton_jetton(
    *, address: str, amount: Decimal, memo: str
) -> tuple[str | None, str | None]:
    """Build, sign and broadcast a USDT jetton transfer on TON.

    Uses ``pytoniq-core`` for the wallet primitives and toncenter for the
    broadcast. The private key never leaves this process and is never logged.
    """
    try:
        from pytoniq_core import Address, Cell, begin_cell  # type: ignore[import-not-found]
        from pytoniq_core.crypto.keys import mnemonic_to_private_key  # noqa: F401
    except ImportError:
        return None, (
            "TON payout dependencies are not installed in this image. Send the "
            "payout manually and record the transaction hash."
        )

    if not settings.WALLET_2_ADDRESS:
        return None, "The payout wallet address is not configured."

    # USDT on TON has 6 decimals.
    units = int(Decimal(amount) * Decimal(10**6))

    forward_payload: Cell = (
        begin_cell().store_uint(0, 32).store_snake_string(memo).end_cell()
    )
    transfer_body = (
        begin_cell()
        .store_uint(0x0F8A7EA5, 32)          # jetton transfer op code
        .store_uint(0, 64)                    # query id
        .store_coins(units)                   # amount
        .store_address(Address(address))      # destination
        .store_address(Address(settings.WALLET_2_ADDRESS))  # response destination
        .store_bit(0)                         # no custom payload
        .store_coins(1)                       # forward ton amount (1 nanoton)
        .store_bit(1)
        .store_ref(forward_payload)
        .end_cell()
    )

    payload_b64 = transfer_body.to_boc().hex()
    logger.info("payout.prepared address=%s amount=%s", address, amount)

    async with httpx.AsyncClient(
        base_url=settings.TONCENTER_BASE_URL,
        timeout=30.0,
        headers=(
            {"X-API-Key": settings.TONCENTER_API_KEY}
            if settings.TONCENTER_API_KEY
            else {}
        ),
    ) as client:
        response = await client.post("/sendBocReturnHash", json={"boc": payload_b64})
        if response.status_code >= 400:
            return None, f"Broadcast rejected by toncenter: {response.text[:300]}"
        data = response.json()

    if not data.get("ok"):
        return None, f"Broadcast failed: {str(data)[:300]}"

    tx_hash = (data.get("result") or {}).get("hash")
    if not tx_hash:
        return None, "Broadcast accepted but no transaction hash was returned."

    logger.info("payout.sent address=%s amount=%s tx=%s", address, amount, tx_hash)
    return tx_hash, None


async def payout_wallet_balance() -> Decimal | None:
    """Best-effort USDT balance of the payout wallet, for the admin dashboard."""
    if not settings.WALLET_2_ADDRESS:
        return None
    try:
        async with httpx.AsyncClient(
            base_url=settings.TONCENTER_BASE_URL,
            timeout=15.0,
            headers=(
                {"X-API-Key": settings.TONCENTER_API_KEY}
                if settings.TONCENTER_API_KEY
                else {}
            ),
        ) as client:
            response = await client.get(
                "/getAddressBalance", params={"address": settings.WALLET_2_ADDRESS}
            )
            response.raise_for_status()
            data = response.json()
        raw = data.get("result")
        return Decimal(raw) / Decimal(10**9) if raw is not None else None
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("payout.balance_check_failed error=%s", exc)
        return None
