"""Advertiser-facing schemas: campaigns, stats, creative generation."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, HttpUrl, computed_field, field_validator

from app.config import settings
from app.core.enums import AD_LANGUAGES, BUTTON_LABELS
from app.schemas.common import APIModel, RequestModel

FrontendFormat = Literal["channel", "interstitial", "pop"]
FrontendStatus = Literal[
    "pending_review", "active", "paused", "paused_balance", "stopped", "rejected"
]

_URL_RE = re.compile(r"^https://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


def _validate_destination(value: str) -> str:
    """Only https, and never a link back into our own tracker."""
    value = value.strip()
    if not _URL_RE.match(value):
        raise ValueError("Destination URL must be a valid https:// address.")
    if len(value) > 2048:
        raise ValueError("Destination URL is too long.")
    lowered = value.lower()
    for banned in ("javascript:", "data:", "vbscript:"):
        if banned in lowered:
            raise ValueError("Destination URL scheme is not allowed.")
    if "/t/" in lowered and settings.PUBLIC_BASE_URL.lower().replace("https://", "") in lowered:
        raise ValueError("Destination URL cannot point at the AdsKinz tracker.")
    return value


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #
class CampaignCreateRequest(RequestModel):
    name: str = Field(min_length=3, max_length=160)
    format: FrontendFormat = "channel"
    title: str | None = Field(default=None, min_length=3, max_length=56)
    brand_name: str | None = Field(default=None, max_length=40, alias="brandName")
    ad_text: str = Field(min_length=10, max_length=1024, alias="copy")
    button_label: str = Field(max_length=40, alias="buttonLabel")
    destination_url: str = Field(alias="destinationUrl")
    target_language: str = Field(default="all", alias="language")
    # No budget field: every campaign is created with an isolated balance of
    # $0. Funding happens afterwards through the top-up ("add_budget") flow,
    # which is what actually moves money out of the advertiser's wallet.
    daily_budget: Decimal | None = Field(default=None, alias="dailyBudget")
    cpm_bid: Decimal = Field(alias="cpm")
    image_url: str | None = Field(default=None, alias="imageUrl")
    ai_generated: bool = False

    _check_url = field_validator("destination_url")(_validate_destination)

    @field_validator("button_label")
    @classmethod
    def _known_label(cls, value: str) -> str:
        if value not in BUTTON_LABELS:
            raise ValueError("Button label is not part of the allowed set.")
        return value

    @field_validator("target_language")
    @classmethod
    def _known_language(cls, value: str) -> str:
        value = (value or "all").strip().lower()
        if value in AD_LANGUAGES:
            return value
        # The wizard may send display labels ("All languages", "French").
        label_map = {
            "all languages": "all", "english": "en", "french": "fr", "russian": "ru",
            "chinese (simplified)": "zh", "spanish": "es", "portuguese": "pt",
            "arabic": "ar", "hindi": "hi", "indonesian": "id", "turkish": "tr",
            "ukrainian": "uk",
        }
        resolved = label_map.get(value)
        if resolved is None:
            raise ValueError("Unsupported target language.")
        return resolved

    @field_validator("cpm_bid")
    @classmethod
    def _min_cpm(cls, value: Decimal) -> Decimal:
        if value < settings.MIN_CPM_BID:
            raise ValueError(f"CPM bid must be at least ${settings.MIN_CPM_BID}.")
        return value.quantize(Decimal("0.01"))

    @field_validator("daily_budget")
    @classmethod
    def _min_daily(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if value < settings.MIN_DAILY_BUDGET:
            raise ValueError(f"Daily budget must be at least ${settings.MIN_DAILY_BUDGET}.")
        return value.quantize(Decimal("0.01"))


class CampaignUpdateRequest(RequestModel):
    """Partial update. Any change on an active campaign forces re-moderation."""

    name: str | None = Field(default=None, min_length=3, max_length=160)
    title: str | None = Field(default=None, min_length=3, max_length=56)
    brand_name: str | None = Field(default=None, max_length=40, alias="brandName")
    ad_text: str | None = Field(default=None, min_length=10, max_length=1024, alias="copy")
    button_label: str | None = Field(default=None, max_length=40, alias="buttonLabel")
    destination_url: str | None = Field(default=None, alias="destinationUrl")
    target_language: str | None = Field(default=None, alias="language")
    total_budget: Decimal | None = Field(default=None, alias="budget")
    daily_budget: Decimal | None = Field(default=None, alias="dailyBudget")
    cpm_bid: Decimal | None = Field(default=None, alias="cpm")
    image_url: str | None = Field(default=None, alias="imageUrl")
    # Only 'paused' and 'stopped' may be set by the advertiser.
    status: Literal["paused", "active", "stopped"] | None = None
    # Moves money out of the advertiser's wallet into this campaign's isolated
    # balance (the "Top up" / "Recharger" button). This is the only way a
    # campaign's budget actually increases.
    add_budget: Decimal | None = Field(default=None, alias="addBudget", gt=0)

    @field_validator("destination_url")
    @classmethod
    def _check_url(cls, value: str | None) -> str | None:
        return _validate_destination(value) if value else None

    @field_validator("button_label")
    @classmethod
    def _known_label(cls, value: str | None) -> str | None:
        if value and value not in BUTTON_LABELS:
            raise ValueError("Button label is not part of the allowed set.")
        return value

    @field_validator("total_budget")
    @classmethod
    def _budget_not_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("Total budget cannot be negative.")
        return value

    @field_validator("add_budget")
    @classmethod
    def _min_topup(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < settings.MIN_CAMPAIGN_TOPUP:
            raise ValueError(f"A top-up must be at least ${settings.MIN_CAMPAIGN_TOPUP}.")
        return value

    @field_validator("cpm_bid")
    @classmethod
    def _min_cpm(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < settings.MIN_CPM_BID:
            raise ValueError(f"CPM bid must be at least ${settings.MIN_CPM_BID}.")
        return value


class GenerateCopyRequest(RequestModel):
    brief: str = Field(min_length=3, max_length=600)
    language: str = Field(default="en", max_length=8)
    tone: Literal["neutral", "punchy", "premium", "playful"] = "punchy"


class ImageUploadRequest(RequestModel):
    content_type: str = Field(alias="contentType", max_length=64)


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #
class CampaignResponse(APIModel):
    """Field names mirror the frontend's ``Campaign`` type in mock-data.ts."""

    id: str
    name: str
    language: str
    status: FrontendStatus
    format: FrontendFormat
    cpm: Decimal
    budget: Decimal
    spent: Decimal
    clicks: int
    impressions: int
    rejectionReason: str | None = None

    # Extra fields the detail view uses; harmless for the list view.
    dailyBudget: Decimal | None = None
    destinationUrl: str | None = None
    buttonLabel: str | None = None
    title: str | None = None
    brandName: str | None = None
    ad_copy: str | None = Field(default=None, alias="copy", serialization_alias="copy")
    imageUrl: str | None = None
    trackingId: str | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None
    approvedAt: datetime | None = None
    aiGenerated: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def remaining(self) -> Decimal:
        return max(Decimal("0.00"), self.budget - self.spent)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ctr(self) -> float:
        return round(self.clicks / self.impressions * 100, 2) if self.impressions else 0.0


class CampaignListResponse(APIModel):
    items: list[CampaignResponse]
    total: int


class AdvertiserStatsResponse(APIModel):
    """Matches ``advertiserSummary`` consumed by the traffic dashboard."""

    balance: Decimal
    activeBudget: Decimal
    totalImpressions: int
    impressionsMonth: int
    clicks30: int
    ctr: float
    spend: Decimal
    activeCampaigns: int = 0
    pendingCampaigns: int = 0
    daily: list[float] = Field(default_factory=list)


class GenerateCopyResponse(APIModel):
    ad_copy: str = Field(alias="copy", serialization_alias="copy")
    model_name: str = Field(alias="model", serialization_alias="model")
    tokens_used: int | None = None


class TranslationItem(APIModel):
    lang_code: str
    translated_text: str
    translated_button_label: str | None = None


class CampaignTranslationsResponse(APIModel):
    campaign_id: uuid.UUID
    source_language: str
    generated: bool
    translations: list[TranslationItem]
