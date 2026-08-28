"""Publisher-facing schemas: channels, mini apps, withdrawals."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator

from app.config import settings
from app.core.enums import AD_LANGUAGES, MiniAppFormat
from app.schemas.common import APIModel, RequestModel

FrontendChannelStatus = Literal[
    "pending_moderation", "approved_not_started", "building_trust",
    "active", "suspended", "rejected",
]
FrontendMiniAppStatus = Literal["pending_moderation", "active", "suspended", "rejected"]

# The frontend enforces the same shape before submitting.
TON_ADDRESS_RE = re.compile(r"^U[Qf][A-Za-z0-9_-]{10,}$")
TG_LINK_RE = re.compile(r"^https://t\.me/[A-Za-z0-9_+/-]+$", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Channels
# --------------------------------------------------------------------------- #
class ChannelCreateRequest(RequestModel):
    name: str = Field(min_length=settings.MIN_CHANNEL_NAME_LENGTH, max_length=160)
    public_link: str = Field(alias="publicLink")
    private_invite_link: str = Field(default="", alias="privateLink")
    admin_username: str = Field(default="", alias="adminUsername", max_length=64)
    logo_url: str | None = Field(default=None, alias="logoUrl")
    declared_language: str = Field(alias="language")
    max_ads_per_day: int = Field(default=1, alias="maxAdsPerDay")
    preferred_hours_utc: list[int] | None = Field(default=None, alias="preferredHours")
    description: str | None = Field(default=None, max_length=600)

    @field_validator("logo_url")
    @classmethod
    def _logo(cls, value: str | None) -> str | None:
        value = (value or "").strip() or None
        if value and not value.startswith("https://"):
            raise ValueError("Logo URL must be a valid https:// address.")
        return value

    @field_validator("public_link", "private_invite_link")
    @classmethod
    def _telegram_link(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            return ""
        if not TG_LINK_RE.match(value):
            raise ValueError("Link must be a valid https://t.me/... Telegram URL.")
        return value

    @field_validator("admin_username")
    @classmethod
    def _handle(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            return ""
        if not value.startswith("@"):
            value = f"@{value}"
        if not re.fullmatch(r"@[A-Za-z0-9_]{4,32}", value):
            raise ValueError("Admin username must be a valid Telegram handle.")
        return value

    @field_validator("declared_language")
    @classmethod
    def _language(cls, value: str) -> str:
        value = (value or "").strip().lower()
        if value not in AD_LANGUAGES or value == "all":
            raise ValueError("Declared language must be one specific supported language.")
        return value

    @field_validator("max_ads_per_day")
    @classmethod
    def _frequency(cls, value: int) -> int:
        if not 0 <= value <= settings.MAX_ADS_PER_DAY:
            raise ValueError(f"Ads per day must be between 0 and {settings.MAX_ADS_PER_DAY}.")
        return value

    @field_validator("preferred_hours_utc")
    @classmethod
    def _hours(cls, value: list[int] | None) -> list[int] | None:
        if not value:
            return None
        if any(h < 0 or h > 23 for h in value):
            raise ValueError("Preferred hours must be UTC hours between 0 and 23.")
        return sorted(set(value))


class ChannelResponse(APIModel):
    id: str
    name: str
    language: str
    subscribers: int
    subscribersUpdatedAt: datetime | None = None
    status: FrontendChannelStatus
    publicLink: str | None = None
    privateLink: str | None = None
    adminUsername: str | None = None
    logoUrl: str | None = None
    maxAdsPerDay: int = 1
    effectiveMaxAdsPerDay: int = 1
    preferredHours: list[int] | None = None
    rejectionReason: str | None = None
    botAdminVerified: bool = False
    trustHoursLeft: int = 0
    trustEndsAt: datetime | None = None
    impressions: int = 0
    earnings: Decimal = Decimal("0.00")
    adsToday: int = 0
    createdAt: datetime | None = None
    approvedAt: datetime | None = None
    startedAt: datetime | None = None


class ChannelStatsResponse(APIModel):
    """Everything the channel detail screen needs in one call."""

    channelId: str
    status: FrontendChannelStatus
    subscribers: int
    subscribersUpdatedAt: datetime | None = None
    lifetimeImpressions: int
    lifetimeClicks: int
    lifetimeEarnings: Decimal
    ctr: float
    effectiveCpm: Decimal
    last24hImpressions: int
    last24hClicks: int
    last24hEarnings: Decimal
    adsToday: int
    maxAdsPerDay: int
    effectiveMaxAdsPerDay: int
    livePostsCount: int
    botAdminVerified: bool
    trustHoursLeft: int = 0


class ChannelListResponse(APIModel):
    items: list[ChannelResponse]
    total: int


class BotStatusItem(APIModel):
    channelId: str
    name: str
    isAdmin: bool
    canPost: bool
    canDelete: bool
    checkedAt: datetime | None = None
    error: str | None = None


class BotStatusResponse(APIModel):
    botUsername: str
    items: list[BotStatusItem]
    allVerified: bool


class LogoUploadRequest(RequestModel):
    content_type: str = Field(alias="contentType", max_length=64)


class ChannelStartRequest(RequestModel):
    """Publisher pressing "Start" on an approved channel opens the trust window."""

    channel_id: uuid.UUID


# --------------------------------------------------------------------------- #
# Mini Apps
# --------------------------------------------------------------------------- #
class MiniAppCreateRequest(RequestModel):
    name: str = Field(min_length=3, max_length=160)
    url: str
    formats_enabled: list[str] = Field(alias="formats", min_length=1)
    category: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=600)

    @field_validator("url")
    @classmethod
    def _url(cls, value: str) -> str:
        value = (value or "").strip()
        if not (value.startswith("https://") or value.startswith("http://t.me/")):
            raise ValueError("Mini App URL must start with https://")
        return value

    @field_validator("formats_enabled")
    @classmethod
    def _formats(cls, value: list[str]) -> list[str]:
        """Accept every spelling of the two Mini App formats.

        The dashboard sends ``pop``, the SDK query string uses
        ``popInterstitial`` and the enum stores ``pop_interstitial``. All three
        are normalised to the SDK spelling, which is what ``/sdk/serve``
        compares against.
        """
        aliases = {
            "interstitial": "interstitial",
            "pop": "popInterstitial",
            "popinterstitial": "popInterstitial",
            "pop_interstitial": "popInterstitial",
        }
        cleaned = []
        for item in value:
            key = aliases.get(item.strip().lower())
            if key is None:
                raise ValueError("Unsupported ad format for a Mini App.")
            cleaned.append(key)
        return sorted(set(cleaned))


class MiniAppResponse(APIModel):
    id: str
    name: str
    url: str
    status: FrontendMiniAppStatus
    formats: list[str] = Field(default_factory=list)
    kinzKey: str | None = None
    rejectionReason: str | None = None
    integrationDetected: bool = False
    impressions: int = 0
    earnings: Decimal = Decimal("0.00")
    createdAt: datetime | None = None


class MiniAppListResponse(APIModel):
    items: list[MiniAppResponse]
    total: int


class MiniAppKeyResponse(APIModel):
    """Returned by /publisher/mini-apps/:id/key — the Kinz-ID integration key."""

    id: str
    kinzKey: str
    snippet: str
    docsUrl: str


# --------------------------------------------------------------------------- #
# Withdrawals
# --------------------------------------------------------------------------- #
class WithdrawalCreateRequest(RequestModel):
    amount: Decimal
    destination_address: str = Field(alias="address")
    memo_comment: str | None = Field(default=None, alias="memo", max_length=120)

    @field_validator("amount")
    @classmethod
    def _minimum(cls, value: Decimal) -> Decimal:
        if value < settings.MIN_WITHDRAWAL:
            raise ValueError(f"Minimum withdrawal is ${settings.MIN_WITHDRAWAL}.")
        return value.quantize(Decimal("0.01"))

    @field_validator("destination_address")
    @classmethod
    def _address(cls, value: str) -> str:
        value = (value or "").strip()
        if not TON_ADDRESS_RE.match(value):
            raise ValueError("Destination must be a valid TON address (USDT TON only).")
        return value


class WithdrawalResponse(APIModel):
    id: str
    amount: Decimal
    address: str
    memo: str | None = None
    method: str = "USDT TON"
    status: Literal["pending", "approved", "paid", "rejected"]
    rejectionReason: str | None = None
    txHash: str | None = None
    requestedAt: datetime | None = None
    paidAt: datetime | None = None


class WithdrawalListResponse(APIModel):
    items: list[WithdrawalResponse]
    total: int
    availableBalance: Decimal = Decimal("0.00")
    heldBalance: Decimal = Decimal("0.00")
    minimum: Decimal = settings.MIN_WITHDRAWAL
    eligible: bool = False
    eligibleAt: datetime | None = None
    ineligibleReason: str | None = None


class PublisherStatsResponse(APIModel):
    availableBalance: Decimal
    heldBalance: Decimal
    lifetimeEarnings: Decimal
    impressions30: int
    clicks30: int
    activeChannels: int
    activeMiniApps: int
    daily: list[float] = Field(default_factory=list)
