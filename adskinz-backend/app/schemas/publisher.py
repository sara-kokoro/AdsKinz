"""Publisher-facing schemas: channels, mini apps, withdrawals."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator

from app.config import settings
from app.core.enums import AD_LANGUAGES, MiniAppFormat, WEEKDAY_KEYS
from app.schemas.common import APIModel, RequestModel

FrontendChannelStatus = Literal[
    "pending_moderation", "approved_not_started", "building_trust",
    "active", "suspended", "archived", "rejected",
]
FrontendMiniAppStatus = Literal["pending_moderation", "active", "suspended", "archived", "rejected"]

# The frontend enforces the same shape before submitting.
TON_ADDRESS_RE = re.compile(r"^U[Qf][A-Za-z0-9_-]{10,}$")
TG_LINK_RE = re.compile(r"^https://t\.me/[A-Za-z0-9_+/-]+$", re.IGNORECASE)



def validate_preferred_slots(value: dict[str, list[int]] | None) -> dict[str, list[int]] | None:
    """``value`` holds UTC minute-of-day slots on a 30-minute grid (0, 30,
    60, ... 1410) — not hours. This must stay in sync with the frontend's
    HALF_HOUR_SLOTS (src/components/kit.tsx) and with the consumer in
    app/services/ad_selection_service.py, which floors "now" onto the same
    grid before comparing.
    """
    if not value:
        return None
    cleaned: dict[str, list[int]] = {}
    for day, minutes in value.items():
        if day not in WEEKDAY_KEYS:
            raise ValueError(f"Unknown weekday '{day}'. Use one of: {', '.join(WEEKDAY_KEYS)}.")
        if not minutes:
            continue
        if any(m < 0 or m > 1439 or m % 30 != 0 for m in minutes):
            raise ValueError(
                "Preferred slots must be UTC minute-of-day values on a 30-minute grid "
                "(0 to 1439, in steps of 30)."
            )
        cleaned[day] = sorted(set(minutes))
    return cleaned or None


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
    preferred_slots: dict[str, list[int]] | None = Field(default=None, alias="preferredSlots")
    description: str | None = Field(default=None, max_length=600)
    # Optional: publisher picks it from our custom dropdown. If omitted, the
    # server auto-detects it (keywords first, AI fallback) on creation.
    category: str | None = Field(default=None, alias="category")

    @field_validator("category")
    @classmethod
    def _known_category(cls, value: str | None) -> str | None:
        from app.core.enums import CHANNEL_CATEGORIES

        if value is None or value == "":
            return None
        if value not in CHANNEL_CATEGORIES:
            raise ValueError("Unknown channel category.")
        return value

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

    @field_validator("preferred_slots")
    @classmethod
    def _slots(cls, value: dict[str, list[int]] | None) -> dict[str, list[int]] | None:
        return validate_preferred_slots(value)


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
    category: str | None = None
    categorySource: str | None = None
    maxAdsPerDay: int = 1
    effectiveMaxAdsPerDay: int = 1
    preferredSlots: dict[str, list[int]] | None = None
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
    original_url: str | None = Field(default=None, alias="originalUrl", max_length=2048)
    bot_id: str | None = Field(default=None, alias="botId", max_length=64)
    bot_username: str | None = Field(default=None, alias="botUsername", max_length=64)
    bot_token: str | None = Field(default=None, alias="botToken", max_length=200)
    formats_enabled: list[str] = Field(alias="formats", min_length=1)
    category: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=600)

    @field_validator("url", "original_url")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not (value.startswith("https://") or value.startswith("http://t.me/")):
            raise ValueError("Mini App URL must start with https://")
        return value

    @field_validator("bot_username")
    @classmethod
    def _bot_username(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        if not value:
            return None
        if not value.startswith("@"):
            value = f"@{value}"
        if not re.fullmatch(r"@[A-Za-z0-9_]{4,32}", value):
            raise ValueError("Bot username must be a valid Telegram handle.")
        return value

    @field_validator("bot_token")
    @classmethod
    def _bot_token(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        return value or None

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
    originalUrl: str | None = None
    botId: str | None = None
    botUsername: str | None = None
    botVerificationEnabled: bool = False
    status: FrontendMiniAppStatus
    formats: list[str] = Field(default_factory=list)
    kinzKey: str | None = None
    rejectionReason: str | None = None
    integrationDetected: bool = False
    impressions: int = 0
    earnings: Decimal = Decimal("0.00")
    createdAt: datetime | None = None
    archivedAt: datetime | None = None


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
