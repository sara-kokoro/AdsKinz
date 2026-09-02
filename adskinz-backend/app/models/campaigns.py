"""Campaign and creative-translation models."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.core.enums import CampaignFormat, CampaignStatus
from app.database import Base, TimestampMixin, UUIDPrimaryKeyMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from app.models.accounts import Advertiser
    from app.models.tracking import Click, ScheduledPost


class Campaign(Base, UUIDPrimaryKeyMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint(
            "format IN ('native_post', 'interstitial', 'pop_interstitial')",
            name="format_valid",
        ),
        CheckConstraint(
            "status IN ('pending_review', 'active', 'paused', "
            "'paused_insufficient_balance', 'stopped', 'rejected')",
            name="status_valid",
        ),
        CheckConstraint("cpm_bid >= 2.00", name="cpm_min"),
        CheckConstraint("total_budget >= 20.00", name="budget_min"),
        CheckConstraint(
            "daily_budget IS NULL OR daily_budget >= 2.00", name="daily_budget_min"
        ),
        CheckConstraint("spent_usd >= 0", name="spent_non_negative"),
        Index("ix_campaigns_advertiser_status", "advertiser_id", "status"),
        # Covering index for the ad auction: status + format + language, ordered by bid.
        Index("ix_campaigns_auction", "status", "format", "target_language", "cpm_bid"),
    )

    advertiser_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("advertisers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False, default="Untitled campaign")
    format: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CampaignStatus.PENDING_REVIEW.value,
        server_default=CampaignStatus.PENDING_REVIEW.value,
    )
    target_language: Mapped[str] = mapped_column(
        String(8), nullable=False, default="all", server_default="all"
    )

    # Creative
    image_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(56))
    brand_name: Mapped[str | None] = mapped_column(String(40))
    ad_text: Mapped[str] = mapped_column(Text, nullable=False)
    ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    button_label: Mapped[str] = mapped_column(String(40), nullable=False)
    destination_url: Mapped[str] = mapped_column(Text, nullable=False)

    # Economics
    cpm_bid: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    total_budget: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    daily_budget: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    spent_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )

    # Counters (denormalised for dashboard reads)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Moderation
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL")
    )
    translations_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    submitted_ip_hash: Mapped[str | None] = mapped_column(String(64))

    # Set when we email the advertiser that this campaign's remaining budget
    # dropped under settings.CAMPAIGN_LOW_BALANCE_THRESHOLD; cleared once the
    # campaign is topped back up above it, so the alert can fire again later.
    low_balance_alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    advertiser: Mapped["Advertiser"] = relationship(back_populates="campaigns", lazy="joined")
    translations: Mapped[list["CampaignTranslation"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", lazy="selectin"
    )
    scheduled_posts: Mapped[list["ScheduledPost"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", lazy="noload"
    )
    clicks_rel: Mapped[list["Click"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", lazy="noload"
    )
    daily_spends: Mapped[list["CampaignDailySpend"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", lazy="noload"
    )

    # ------------------------------------------------------------------ #
    # Derived properties
    # ------------------------------------------------------------------ #
    @property
    def remaining_budget(self) -> Decimal:
        return max(Decimal("0.00"), self.total_budget - self.spent_usd)

    @property
    def is_exhausted(self) -> bool:
        return self.spent_usd >= self.total_budget

    @property
    def ctr(self) -> float:
        return round(self.clicks / self.impressions * 100, 4) if self.impressions else 0.0

    @property
    def cost_per_impression(self) -> Decimal:
        """CPM is priced per 1000 impressions."""
        return (self.cpm_bid / Decimal("1000")).quantize(Decimal("0.000001"))

    def is_servable(self) -> bool:
        return self.status == CampaignStatus.ACTIVE.value and not self.is_exhausted

    def matches_language(self, lang: str | None) -> bool:
        if self.target_language == "all":
            return True
        return bool(lang) and self.target_language == lang

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Campaign {self.name} {self.status}>"


class CampaignTranslation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Creative text pre-translated at approval time.

    Nothing translates at impression time — the serving path only reads.
    """

    __tablename__ = "campaign_translations"
    __table_args__ = (
        UniqueConstraint("campaign_id", "lang_code", name="uq_campaign_translations_campaign_lang"),
        Index("ix_campaign_translations_lookup", "campaign_id", "lang_code"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    lang_code: Mapped[str] = mapped_column(String(8), nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_button_label: Mapped[str | None] = mapped_column(String(60))
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="groq", server_default="groq")

    campaign: Mapped["Campaign"] = relationship(back_populates="translations")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CampaignTranslation {self.lang_code}>"


class CampaignDailySpend(Base, UUIDPrimaryKeyMixin):
    """Per-day spend, used to enforce ``daily_budget`` without scanning events."""

    __tablename__ = "campaign_daily_spend"
    __table_args__ = (
        UniqueConstraint("campaign_id", "spend_date", name="uq_campaign_daily_spend_campaign_date"),
        Index("ix_campaign_daily_spend_date", "spend_date"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    spend_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    campaign: Mapped["Campaign"] = relationship(back_populates="daily_spends")


def campaign_format_from_frontend(value: str) -> str:
    """Map the frontend's wizard format values onto the storage enum."""
    return {
        "channel": CampaignFormat.NATIVE_POST.value,
        "native_post": CampaignFormat.NATIVE_POST.value,
        "interstitial": CampaignFormat.INTERSTITIAL.value,
        "pop": CampaignFormat.POP_INTERSTITIAL.value,
        "popInterstitial": CampaignFormat.POP_INTERSTITIAL.value,
        "pop_interstitial": CampaignFormat.POP_INTERSTITIAL.value,
    }.get(value, value)


def campaign_format_to_frontend(value: str) -> str:
    return {
        CampaignFormat.NATIVE_POST.value: "channel",
        CampaignFormat.INTERSTITIAL.value: "interstitial",
        CampaignFormat.POP_INTERSTITIAL.value: "pop",
    }.get(value, value)


def campaign_status_to_frontend(value: str) -> str:
    """The frontend uses `paused_balance`; storage uses the explicit form."""
    if value == CampaignStatus.PAUSED_INSUFFICIENT_BALANCE.value:
        return "paused_balance"
    return value


def utc_today() -> date:
    return datetime.now(UTC).date()


__all__ = [
    "Campaign",
    "CampaignDailySpend",
    "CampaignTranslation",
    "campaign_format_from_frontend",
    "campaign_format_to_frontend",
    "campaign_status_to_frontend",
    "settings",
    "utc_today",
]
