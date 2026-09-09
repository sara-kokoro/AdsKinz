"""Account models: advertisers, publishers and admin users."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Sequence,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin, UUIDPrimaryKeyMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from app.models.campaigns import Campaign
    from app.models.finance import Deposit, Withdrawal
    from app.models.placements import Channel, MiniApp

# Each advertiser gets a unique, monotonically increasing HD derivation index.
hd_wallet_index_seq = Sequence("hd_wallet_index_seq", start=1, increment=1)


class Advertiser(Base, UUIDPrimaryKeyMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "advertisers"
    __table_args__ = (
        CheckConstraint("balance_usd >= 0", name="balance_non_negative"),
        Index("ix_advertisers_email_lower", "email", unique=True),
    )

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    telegram_username: Mapped[str | None] = mapped_column(String(64))
    country: Mapped[str | None] = mapped_column(String(64))

    balance_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )
    lifetime_spend_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )

    # Derivation index for TRC20 / BEP20 deposit addresses. Never reused.
    hd_wallet_index: Mapped[int] = mapped_column(
        Integer, hd_wallet_index_seq, unique=True, nullable=False,
        server_default=hd_wallet_index_seq.next_value(),
    )

    # Premium tier (AI poster/creative generation for ad campaigns, $9.99/mo
    # — charged against balance_usd, see billing_service.charge_premium).
    is_premium: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    premium_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    premium_auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    # Referral program: this advertiser's own shareable code, and who
    # referred them in (if anyone). The referrer earns REFERRAL_ADVERTISER_RATE
    # of every deposit this account makes — see billing_service.credit_deposit.
    referral_code: Mapped[str | None] = mapped_column(String(16), unique=True)
    referred_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("advertisers.id", ondelete="SET NULL")
    )

    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    email_verification_code: Mapped[str | None] = mapped_column(String(8))
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_ip_hash: Mapped[str | None] = mapped_column(String(64))
    low_balance_alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    campaigns: Mapped[list["Campaign"]] = relationship(
        back_populates="advertiser", cascade="all, delete-orphan", lazy="selectin"
    )
    deposits: Mapped[list["Deposit"]] = relationship(
        back_populates="advertiser", cascade="all, delete-orphan", lazy="noload"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Advertiser {self.email}>"


class Publisher(Base, UUIDPrimaryKeyMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "publishers"
    __table_args__ = (
        CheckConstraint("available_balance_usd >= 0", name="balance_non_negative"),
        CheckConstraint("held_balance_usd >= 0", name="held_non_negative"),
    )

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    telegram_username: Mapped[str | None] = mapped_column(String(64))
    country: Mapped[str | None] = mapped_column(String(64))

    # Referral program: this publisher's own shareable code, and who
    # referred them in (if anyone). The referrer earns REFERRAL_PUBLISHER_RATE
    # of every earning this account gets — see billing_service.credit_publisher.
    referral_code: Mapped[str | None] = mapped_column(String(16), unique=True)
    referred_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("publishers.id", ondelete="SET NULL")
    )

    # Withdrawable right now.
    available_balance_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )
    # Reserved by a pending or approved withdrawal, not yet paid out.
    held_balance_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )
    lifetime_earnings_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default="0"
    )

    # Timestamp of the first channel approval — starts the withdrawal cooldown.
    first_channel_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    email_verification_code: Mapped[str | None] = mapped_column(String(8))
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_ip_hash: Mapped[str | None] = mapped_column(String(64))

    channels: Mapped[list["Channel"]] = relationship(
        back_populates="publisher", cascade="all, delete-orphan", lazy="noload"
    )
    mini_apps: Mapped[list["MiniApp"]] = relationship(
        back_populates="publisher", cascade="all, delete-orphan", lazy="noload"
    )
    withdrawals: Mapped[list["Withdrawal"]] = relationship(
        back_populates="publisher", cascade="all, delete-orphan", lazy="noload"
    )

    @property
    def total_balance_usd(self) -> Decimal:
        return self.available_balance_usd + self.held_balance_usd

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Publisher {self.email}>"


class AdminUser(Base, UUIDPrimaryKeyMixin, TimestampMixin, UpdatedAtMixin):
    """Single operator account (kingcey). No public sign-up endpoint exists."""

    __tablename__ = "admin_users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # Legacy TOTP fields, unused by the current email-code + fixed-password
    # login flow (kept nullable so old rows and the create_admin script
    # don't need to change shape).
    totp_secret: Mapped[str | None] = mapped_column(Text)
    totp_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_ip_hash: Mapped[str | None] = mapped_column(String(64))
    # Guards against TOTP code replay within the same 30s step. Unused now.
    last_totp_counter: Mapped[int | None] = mapped_column(Integer)
    # One-time 8-digit sign-in code, emailed via Resend on "Ask code".
    # Hashed the same way as a password; cleared the moment it's consumed
    # or expires, so it can never be replayed.
    login_code_hash: Mapped[str | None] = mapped_column(Text)
    login_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AdminUser {self.email}>"


class RefreshToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Stored refresh-token metadata so tokens can be revoked server-side.

    The actual token is a JWT issued to the client; this table stores the
    matching ``jti`` claim. A token is accepted by ``POST /auth/refresh`` only
    while its ``jti`` row exists and has not expired.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_account", "account_type", "account_id"),
        Index("ix_refresh_tokens_expires", "expires_at"),
    )

    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    # JWT ID (jti claim). The client never sees this value.
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RefreshToken {self.account_type} {self.account_id}>"


class LedgerEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Append-only movement log behind every balance mutation.

    Nothing in the system changes ``balance_usd`` or ``available_balance_usd``
    without writing a matching row here, which makes balances reconstructible
    and auditable.
    """

    __tablename__ = "ledger_entries"
    __table_args__ = (
        Index("ix_ledger_account", "account_type", "account_id", "created_at"),
        Index("ix_ledger_ref", "reference_type", "reference_id"),
    )

    account_type: Mapped[str] = mapped_column(String(20), nullable=False)  # advertiser | publisher | campaign | platform
    account_id: Mapped[uuid.UUID | None] = mapped_column()
    entry_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # Positive credits the account, negative debits it.
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    balance_after_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    reference_type: Mapped[str | None] = mapped_column(String(40))
    reference_id: Mapped[uuid.UUID | None] = mapped_column()
    description: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LedgerEntry {self.entry_type} {self.amount_usd}>"
