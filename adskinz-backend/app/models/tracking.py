"""Delivery and tracking models: scheduled posts, view snapshots, clicks,
impressions, anomalies and the admin audit log."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.campaigns import Campaign
    from app.models.placements import Channel


class ScheduledPost(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A native ad published into a Telegram channel by @AdsKinzBot.

    ``delete_at`` is always ``posted_at + 24h``. The cleanup job is fully
    independent from budget tracking: a post is removed after 24 hours even if
    the campaign still has budget, and a campaign can run out of budget without
    the live post being taken down early.
    """

    __tablename__ = "scheduled_posts"
    __table_args__ = (
        Index("ix_scheduled_posts_pending_delete", "delete_at", "deleted"),
        Index("ix_scheduled_posts_channel_posted", "channel_id", "posted_at"),
        Index("ix_scheduled_posts_campaign", "campaign_id"),
        Index("ix_scheduled_posts_active_views", "deleted", "posted_at"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )

    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    tracking_id: Mapped[uuid.UUID | None] = mapped_column(unique=True, index=True)

    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delete_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delete_error: Mapped[str | None] = mapped_column(Text)
    post_error: Mapped[str | None] = mapped_column(Text)

    # Cumulative view count at the last poll, and how many views were billed.
    last_view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    billed_views: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    revenue_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    language_served: Mapped[str | None] = mapped_column(String(8))

    campaign: Mapped["Campaign"] = relationship(back_populates="scheduled_posts", lazy="joined")
    channel: Mapped["Channel"] = relationship(back_populates="scheduled_posts", lazy="joined")
    snapshots: Mapped[list["ViewSnapshot"]] = relationship(
        back_populates="scheduled_post", cascade="all, delete-orphan", lazy="noload"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ScheduledPost msg={self.telegram_message_id}>"


class ViewSnapshot(Base, UUIDPrimaryKeyMixin):
    """A cumulative view reading taken by the MTProto watcher.

    Billing uses the delta between two consecutive snapshots, never the raw
    cumulative figure.
    """

    __tablename__ = "view_snapshots"
    __table_args__ = (
        CheckConstraint("view_count_cumulative >= 0", name="views_non_negative"),
        Index("ix_view_snapshots_post_polled", "scheduled_post_id", "polled_at"),
    )

    scheduled_post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scheduled_posts.id", ondelete="CASCADE"), nullable=False
    )
    view_count_cumulative: Mapped[int] = mapped_column(Integer, nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    billed_amount_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    polled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    scheduled_post: Mapped["ScheduledPost"] = relationship(back_populates="snapshots")


class Impression(Base, UUIDPrimaryKeyMixin):
    """One Mini App ad serve. Channel impressions are counted via view deltas."""

    __tablename__ = "impressions"
    __table_args__ = (
        Index("ix_impressions_campaign_served", "campaign_id", "served_at"),
        Index("ix_impressions_placement", "placement_type", "placement_id", "served_at"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    tracking_id: Mapped[uuid.UUID] = mapped_column(unique=True, nullable=False, index=True)
    placement_type: Mapped[str] = mapped_column(String(16), nullable=False)  # miniapp | channel
    placement_id: Mapped[uuid.UUID | None] = mapped_column()
    format: Mapped[str | None] = mapped_column(String(24))
    lang_served: Mapped[str | None] = mapped_column(String(8))
    billed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    billed_amount_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    ip_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    served_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()", index=True
    )


class Click(Base, UUIDPrimaryKeyMixin):
    """A click on a tracked ad button.

    Suspicious clicks are still redirected — only billing is skipped.
    """

    __tablename__ = "clicks"
    __table_args__ = (
        CheckConstraint("fraud_score BETWEEN 0 AND 1", name="fraud_score_range"),
        Index("ix_clicks_campaign_time", "campaign_id", "clicked_at"),
        Index("ix_clicks_ip_time", "ip_hash", "clicked_at"),
    )

    tracking_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_post_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scheduled_posts.id", ondelete="SET NULL")
    )
    placement_type: Mapped[str | None] = mapped_column(String(16))
    placement_id: Mapped[uuid.UUID | None] = mapped_column()

    ip_hash: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    referer: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(String(8))
    asn: Mapped[str | None] = mapped_column(String(32))

    fraud_score: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    fraud_reasons: Mapped[list[str] | None] = mapped_column(JSONB)
    billed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    billed_amount_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()", index=True
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="clicks_rel")


class TrackingLink(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Resolves ``/t/{tracking_id}`` to a campaign and its placement context."""

    __tablename__ = "tracking_links"
    __table_args__ = (Index("ix_tracking_links_campaign", "campaign_id"),)

    tracking_id: Mapped[uuid.UUID] = mapped_column(unique=True, nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_post_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scheduled_posts.id", ondelete="SET NULL")
    )
    placement_type: Mapped[str | None] = mapped_column(String(16))
    placement_id: Mapped[uuid.UUID | None] = mapped_column()
    destination_url: Mapped[str] = mapped_column(Text, nullable=False)
    click_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Anomaly(Base, UUIDPrimaryKeyMixin):
    """Anti-fraud finding surfaced in the admin console."""

    __tablename__ = "anomalies"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 1", name="score_range"),
        Index("ix_anomalies_detected", "detected_at"),
        Index("ix_anomalies_subject", "kind", "subject_id"),
    )

    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # campaign | channel | mini_app | publisher
    subject_id: Mapped[uuid.UUID | None] = mapped_column()
    subject_label: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )


class AuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Every sensitive admin action, append-only."""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_created", "created_at"),
        Index("ix_audit_log_target", "target_type", "target_id"),
    )

    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL")
    )
    actor_label: Mapped[str] = mapped_column(String(120), nullable=False, default="kingcey")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[uuid.UUID | None] = mapped_column()
    target_label: Mapped[str | None] = mapped_column(String(240))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip_hash: Mapped[str | None] = mapped_column(String(64))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog {self.action} {self.target_label}>"


class Dispute(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Advertiser or publisher complaint handled from the admin console."""

    __tablename__ = "disputes"
    __table_args__ = (Index("ix_disputes_status_created", "status", "created_at"),)

    opened_by_type: Mapped[str] = mapped_column(String(16), nullable=False)
    opened_by_id: Mapped[uuid.UUID | None] = mapped_column()
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    related_type: Mapped[str | None] = mapped_column(String(32))
    related_id: Mapped[uuid.UUID | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", server_default="open")
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
