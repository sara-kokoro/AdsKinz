"""Placement models: Telegram channels and Mini Apps."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.core.enums import ChannelStatus, MiniAppStatus
from app.database import Base, TimestampMixin, UUIDPrimaryKeyMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from app.models.accounts import Publisher
    from app.models.tracking import ScheduledPost


class Channel(Base, UUIDPrimaryKeyMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "channels"
    __table_args__ = (
        CheckConstraint("char_length(name) >= 5", name="name_min_length"),
        CheckConstraint("subscriber_count >= 500", name="subscribers_min"),
        CheckConstraint("max_ads_per_day BETWEEN 0 AND 3", name="ads_per_day_range"),
        CheckConstraint(
            "status IN ('pending_moderation', 'approved_not_started', "
            "'active_building_trust', 'active', 'suspended', 'rejected')",
            name="status_valid",
        ),
        Index("ix_channels_publisher_status", "publisher_id", "status"),
        Index("ix_channels_delivery", "status", "declared_language"),
    )

    publisher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publishers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    public_link: Mapped[str] = mapped_column(Text, nullable=False)
    private_invite_link: Mapped[str] = mapped_column(Text, nullable=False, default="")
    admin_username: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    description: Mapped[str | None] = mapped_column(Text)

    declared_language: Mapped[str] = mapped_column(String(8), nullable=False)
    subscriber_count: Mapped[int] = mapped_column(Integer, nullable=False)
    subscriber_count_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    logo_url: Mapped[str | None] = mapped_column(Text)
    max_ads_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    preferred_hours_utc: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))

    # Telegram identifiers resolved once the bot can see the chat.
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64))

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ChannelStatus.PENDING_MODERATION.value,
        server_default=ChannelStatus.PENDING_MODERATION.value,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    bot_admin_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    bot_admin_last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_ad_posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Rolling counters kept up to date by the delivery pipeline.
    lifetime_impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    lifetime_earnings_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )
    submitted_ip_hash: Mapped[str | None] = mapped_column(String(64))

    publisher: Mapped["Publisher"] = relationship(back_populates="channels", lazy="joined")
    scheduled_posts: Mapped[list["ScheduledPost"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan", lazy="noload"
    )

    # ------------------------------------------------------------------ #
    # Trust window — computed on every read, never stored
    # ------------------------------------------------------------------ #
    def trust_window_ends_at(self) -> datetime | None:
        if not self.started_at:
            return None
        return self.started_at + timedelta(hours=settings.TRUST_WINDOW_HOURS)

    def in_trust_window(self, now: datetime | None = None) -> bool:
        end = self.trust_window_ends_at()
        if end is None:
            return False
        return (now or datetime.now(UTC)) < end

    def trust_hours_left(self, now: datetime | None = None) -> int:
        end = self.trust_window_ends_at()
        if end is None:
            return 0
        delta = end - (now or datetime.now(UTC))
        return max(0, int(delta.total_seconds() // 3600))

    def effective_status(self, now: datetime | None = None) -> str:
        """Resolve `active_building_trust` -> `active` once the window elapses."""
        if self.status != ChannelStatus.ACTIVE_BUILDING_TRUST.value:
            return self.status
        return (
            ChannelStatus.ACTIVE_BUILDING_TRUST.value
            if self.in_trust_window(now)
            else ChannelStatus.ACTIVE.value
        )

    def effective_max_ads_per_day(self, now: datetime | None = None) -> int:
        """Throttled to one ad a day for as long as trust is being built."""
        if self.effective_status(now) == ChannelStatus.ACTIVE_BUILDING_TRUST.value:
            return min(self.max_ads_per_day, settings.TRUST_WINDOW_MAX_ADS_PER_DAY)
        return self.max_ads_per_day

    def accepts_delivery(self, now: datetime | None = None) -> bool:
        return (
            self.status in (s.value for s in ChannelStatus.deliverable())
            and self.bot_admin_verified
            and self.telegram_chat_id is not None
            and self.effective_max_ads_per_day(now) > 0
        )

    def status_for_frontend(self, now: datetime | None = None) -> str:
        """The frontend labels the trust state `building_trust`."""
        eff = self.effective_status(now)
        return "building_trust" if eff == ChannelStatus.ACTIVE_BUILDING_TRUST.value else eff

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Channel {self.name} {self.status}>"


class MiniApp(Base, UUIDPrimaryKeyMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "mini_apps"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_moderation', 'active', 'suspended', 'archived', 'rejected')",
            name="status_valid",
        ),
        Index("ix_mini_apps_publisher_status", "publisher_id", "status"),
    )

    publisher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publishers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    original_url: Mapped[str | None] = mapped_column(Text)
    bot_id: Mapped[str | None] = mapped_column(String(64))
    bot_username: Mapped[str | None] = mapped_column(String(64))
    # Used only server-side to validate Telegram WebApp initData signatures
    # (see app/services/telegram_auth.py) — never returned in an API response.
    bot_token: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)

    # Public integration key used by the Kinz-ID SDK on /sdk/serve.
    kinz_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    formats_enabled: Mapped[list[str]] = mapped_column(ARRAY(String(24)), nullable=False)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=MiniAppStatus.PENDING_MODERATION.value,
        server_default=MiniAppStatus.PENDING_MODERATION.value,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sdk_version: Mapped[str | None] = mapped_column(String(32))
    last_serve_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lifetime_impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    lifetime_earnings_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )
    submitted_ip_hash: Mapped[str | None] = mapped_column(String(64))

    publisher: Mapped["Publisher"] = relationship(back_populates="mini_apps", lazy="joined")

    def supports_format(self, fmt: str) -> bool:
        return fmt in (self.formats_enabled or [])

    def is_servable(self) -> bool:
        return self.status == MiniAppStatus.ACTIVE.value

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MiniApp {self.name} {self.status}>"


class PlacementDailyStat(Base, UUIDPrimaryKeyMixin):
    """Daily rollup per placement, feeding the publisher dashboard charts."""

    __tablename__ = "placement_daily_stats"
    __table_args__ = (
        Index(
            "ix_placement_daily_unique",
            "placement_type",
            "placement_id",
            "stat_date",
            unique=True,
        ),
    )

    placement_type: Mapped[str] = mapped_column(String(16), nullable=False)  # channel | miniapp
    placement_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    stat_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    earnings_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    ads_delivered: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
