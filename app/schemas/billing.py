"""Billing schemas: deposit addresses and deposit history."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.config import settings
from app.schemas.common import APIModel

Network = Literal["ton", "trc20", "bnb"]


class DepositAddressResponse(APIModel):
    """One watch-only address per advertiser and network.

    TON reuses a single platform address plus a per-advertiser ``memo``; TRC20
    and BNB use a freshly derived address from the corresponding xpub.
    """

    network: Network
    label: str
    address: str
    memo: str | None = None
    memo_required: bool = False
    qr_payload: str
    min_deposit: Decimal = Decimal("1.00")
    fee_usdt: Decimal = Decimal("0.00")
    fee_note: str | None = None
    confirmations_required: int = 1
    warning: str


class DepositItem(APIModel):
    id: str
    network: Network
    networkLabel: str
    amount: Decimal | None = None
    grossAmount: Decimal | None = None
    fee: Decimal = Decimal("0.00")
    status: Literal["awaiting_confirmation", "confirmed"]
    txHash: str | None = None
    address: str | None = None
    memo: str | None = None
    createdAt: datetime | None = None
    confirmedAt: datetime | None = None


class DepositListResponse(APIModel):
    items: list[DepositItem]
    total: int
    balance: Decimal = Decimal("0.00")


class BalanceResponse(APIModel):
    balance: Decimal
    activeBudget: Decimal
    lifetimeSpend: Decimal
    lowBalance: bool = False
    lowBalanceThreshold: Decimal = Decimal("0.00")


NETWORK_LABELS: dict[str, str] = {
    "ton": "USDT TON",
    "trc20": "USDT TRC20",
    "bnb": "USDT BNB (BEP20)",
}

NETWORK_WARNINGS: dict[str, str] = {
    "ton": (
        "Send USDT on the TON network only, and include the memo/comment exactly "
        "as shown. A deposit without the memo cannot be credited automatically."
    ),
    "trc20": (
        f"Send USDT on the TRON (TRC20) network only. A network fee of "
        f"{settings.TRC20_DEPOSIT_FEE_USDT} USDT is deducted before crediting."
    ),
    "bnb": (
        "Send USDT on the BNB Smart Chain (BEP20) network only. Sending any other "
        "token or using another network will result in a permanent loss of funds."
    ),
}


class LedgerItem(APIModel):
    id: str
    type: str
    amount: Decimal
    balanceAfter: Decimal | None = None
    description: str | None = None
    createdAt: datetime | None = None


class LedgerResponse(APIModel):
    items: list[LedgerItem] = Field(default_factory=list)
    total: int = 0
