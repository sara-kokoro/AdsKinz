"""Admin console schemas: moderation queues, finances, anomalies, audit."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, field_validator

from app.schemas.common import APIModel, RequestModel


# --------------------------------------------------------------------------- #
# Moderation actions
# --------------------------------------------------------------------------- #
class ApproveRequest(RequestModel):
    note: str | None = Field(default=None, max_length=500)


class RejectRequest(RequestModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A rejection reason is required.")
        return value


class ModerationActionResponse(APIModel):
    id: str
    status: str
    message: str
    reason: str | None = None


# --------------------------------------------------------------------------- #
# BEP20 sweeps
# --------------------------------------------------------------------------- #
class Bep20SweepItem(APIModel):
    id: str
    depositId: str
    advertiserEmail: str
    derivedAddress: str
    derivationIndex: int
    treasuryAddress: str
    grossAmountUsd: Decimal | None
    sweptAmountUsd: Decimal | None
    gasTopupTxHash: str | None
    sweepTxHash: str | None
    dustReturnTxHash: str | None
    status: str
    error: str | None
    createdAt: datetime
    updatedAt: datetime


class Bep20SweepListResponse(APIModel):
    items: list[Bep20SweepItem]
    total: int


class Bep20SweepRetryResponse(APIModel):
    id: str
    status: str
    message: str


# --------------------------------------------------------------------------- #
# Queues
# --------------------------------------------------------------------------- #
class QueueCampaignItem(APIModel):
    id: str
    name: str
    advertiser: str
    advertiserId: str
    format: str
    language: str
    cpm: Decimal
    budget: Decimal
    ad_copy: str = Field(alias="copy", serialization_alias="copy")
    buttonLabel: str
    destinationUrl: str
    imageUrl: str | None = None
    submittedAt: datetime | None = None
    isEdit: bool = False


class QueueChannelItem(APIModel):
    id: str
    name: str
    publisher: str
    publisherId: str
    language: str
    subscribers: int
    publicLink: str | None = None
    privateLink: str | None = None
    adminUsername: str | None = None
    maxAdsPerDay: int = 1
    botAdminVerified: bool = False
    submittedAt: datetime | None = None


class QueueMiniAppItem(APIModel):
    id: str
    name: str
    publisher: str
    publisherId: str
    url: str
    formats: list[str] = Field(default_factory=list)
    submittedAt: datetime | None = None


class QueueWithdrawalItem(APIModel):
    id: str
    publisher: str
    publisherId: str
    amount: Decimal
    address: str
    memo: str | None = None
    method: str = "USDT TON"
    availableBalance: Decimal = Decimal("0.00")
    lifetimeEarnings: Decimal = Decimal("0.00")
    requestedAt: datetime | None = None


class QueueResponse(APIModel):
    items: list[Any]
    total: int
    counts: dict[str, int] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Full catalogs (all statuses, searchable) — distinct from the queues above,
# which only ever show items awaiting moderation.
# --------------------------------------------------------------------------- #
class AdminChannelItem(APIModel):
    id: str
    name: str
    status: str
    publisherEmail: str
    publisherId: str
    subscribers: int
    publicLink: str | None = None
    telegramUsername: str | None = None
    lifetimeEarnings: Decimal
    createdAt: datetime | None = None


class AdminChannelListResponse(APIModel):
    items: list[AdminChannelItem]
    total: int


class AdminUserItem(APIModel):
    id: str
    email: str
    displayName: str | None = None
    role: Literal["advertiser", "publisher"]
    isBlocked: bool
    blockedReason: str | None = None
    balance: Decimal
    lifetimeValue: Decimal
    createdAt: datetime | None = None


class AdminUserListResponse(APIModel):
    items: list[AdminUserItem]
    total: int


class AdminUserDetailResponse(AdminUserItem):
    channels: list[AdminChannelItem] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Finances
# --------------------------------------------------------------------------- #
FinancePeriodLiteral = Literal["today", "week", "month", "year", "custom"]


class FinanceSeriesPoint(APIModel):
    date: str
    gross: Decimal
    commission: Decimal
    payouts: Decimal


class FinanceTopEntry(APIModel):
    id: str
    label: str
    amount: Decimal
    secondary: str | None = None


class FinancesResponse(APIModel):
    period: FinancePeriodLiteral
    periodStart: date
    periodEnd: date
    grossRevenue: Decimal
    commission: Decimal
    publisherShare: Decimal
    depositsTotal: Decimal
    withdrawalsPaid: Decimal
    withdrawalsPending: Decimal
    advertiserBalances: Decimal
    publisherLiabilities: Decimal
    netTreasury: Decimal
    impressions: int
    clicks: int
    activeCampaigns: int
    activeChannels: int
    series: list[FinanceSeriesPoint] = Field(default_factory=list)
    topAdvertisers: list[FinanceTopEntry] = Field(default_factory=list)
    topPublishers: list[FinanceTopEntry] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Anomalies & audit
# --------------------------------------------------------------------------- #
class AnomalyItem(APIModel):
    id: str
    kind: str
    subject: str
    subjectId: str | None = None
    reason: str
    score: Decimal
    details: dict[str, Any] | None = None
    resolved: bool = False
    detectedAt: datetime | None = None


class AnomalyListResponse(APIModel):
    items: list[AnomalyItem]
    total: int


class AuditItem(APIModel):
    id: str
    actor: str
    action: str
    target: str | None = None
    targetType: str | None = None
    targetId: str | None = None
    details: dict[str, Any] | None = None
    createdAt: datetime | None = None


class AuditListResponse(APIModel):
    items: list[AuditItem]
    total: int


class AdminOverviewResponse(APIModel):
    pendingCampaigns: int
    pendingChannels: int
    pendingMiniApps: int
    pendingWithdrawals: int
    openAnomalies: int
    activeCampaigns: int
    activeChannels: int
    advertisers: int
    publishers: int
    balanceOwedToPublishers: Decimal
    commissionToday: Decimal


class BlockAccountRequest(RequestModel):
    reason: str = Field(min_length=3, max_length=500)
    blocked: bool = True


class AdminActionTarget(RequestModel):
    target_id: uuid.UUID
