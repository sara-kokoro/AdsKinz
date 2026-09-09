"""Finance models: deposits, withdrawals and platform revenue."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
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

from app.core.enums import DepositStatus, WithdrawalStatus
from app.database import Base, TimestampMixin, UUIDPrimaryKeyMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from app.models.accounts import Advertiser, Publisher


class Deposit(Base, UUIDPrimaryKeyMixin, TimestampMixin, UpdatedAtMixin):
    """An inbound USDT transfer credited to an advertiser balance."""

    __tablename__ = "deposits"
    __table_args__ = (
        CheckConstraint("network IN ('ton', 'trc20', 'bnb')", name="network_valid"),
        CheckConstraint(
            "status IN ('awaiting_confirmation', 'confirmed')", name="status_valid"
        ),
        CheckConstraint("amount_usd IS NULL OR amount_usd >= 0", name="amount_non_negative"),
        Index("ix_deposits_advertiser_created", "advertiser_id", "created_at"),
        Index("ix_deposits_address_network", "derived_address", "network"),
    )

    advertiser_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("advertisers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    network: Mapped[str] = mapped_column(String(8), nullable=False)
    derived_address: Mapped[str] = mapped_column(String(128), nullable=False)
    memo: Mapped[str | None] = mapped_column(String(64), index=True)  # TON only

    # Amount seen on chain, before the network fee deduction.
    gross_amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    # Fee withheld (3.25 USDT on TRC20, per the published pricing).
    fee_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    # Net amount actually credited to the balance.
    amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    tx_hash: Mapped[str | None] = mapped_column(String(128), unique=True)
    block_number: Mapped[int | None] = mapped_column(BigInteger)
    confirmations: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DepositStatus.AWAITING_CONFIRMATION.value,
        server_default=DepositStatus.AWAITING_CONFIRMATION.value,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    credited: Mapped[bool] = mapped_column(
        # Guards against double-crediting if the watcher re-sees a transaction.
        default=False, server_default="false", nullable=False
    )

    advertiser: Mapped["Advertiser"] = relationship(back_populates="deposits", lazy="joined")
    bep20_sweep: Mapped["Bep20Sweep"] = relationship(
        back_populates="deposit", lazy="noload", uselist=False
    )
    trc20_sweep: Mapped["Trc20Sweep"] = relationship(
        back_populates="deposit", lazy="noload", uselist=False
    )

    @property
    def network_label(self) -> str:
        return {"ton": "USDT TON", "trc20": "USDT TRC20", "bnb": "USDT BNB"}.get(
            self.network, self.network.upper()
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Deposit {self.network} {self.amount_usd} {self.status}>"


class Withdrawal(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    """A publisher payout request, settled in USDT on TON."""

    __tablename__ = "withdrawals"
    __table_args__ = (
        CheckConstraint("amount_usd >= 50.00", name="amount_min"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'paid', 'rejected')", name="status_valid"
        ),
        Index("ix_withdrawals_publisher_status", "publisher_id", "status"),
        Index("ix_withdrawals_requested", "requested_at"),
    )

    publisher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publishers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    amount_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    destination_address: Mapped[str] = mapped_column(String(128), nullable=False)
    # Empty means "AdsKinz" is used as the on-chain comment at send time.
    memo_comment: Mapped[str | None] = mapped_column(String(120))
    network: Mapped[str] = mapped_column(String(16), nullable=False, default="ton", server_default="ton")
    method_label: Mapped[str] = mapped_column(
        String(32), nullable=False, default="USDT TON", server_default="USDT TON"
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=WithdrawalStatus.PENDING.value,
        server_default=WithdrawalStatus.PENDING.value,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    tx_hash: Mapped[str | None] = mapped_column(String(128))
    payout_error: Mapped[str | None] = mapped_column(Text)

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL")
    )
    requested_ip_hash: Mapped[str | None] = mapped_column(String(64))

    publisher: Mapped["Publisher"] = relationship(back_populates="withdrawals", lazy="joined")

    @property
    def effective_memo(self) -> str:
        return (self.memo_comment or "").strip() or "AdsKinz"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Withdrawal {self.amount_usd} {self.status}>"


class Bep20Sweep(Base, UUIDPrimaryKeyMixin, TimestampMixin, UpdatedAtMixin):
    """Automatic consolidation of a BEP20 USDT deposit to the treasury.

    Each row tracks the full lifecycle: gas top-up, USDT sweep, and dust
    return. If any step fails the row stays in ``failed`` status so an
    operator can retry or investigate.
    """

    __tablename__ = "bep20_sweeps"
    __table_args__ = (
        Index("ix_bep20_sweeps_deposit", "deposit_id", unique=True),
        Index("ix_bep20_sweeps_status", "status"),
    )

    deposit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deposits.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Source derived address that received the USDT deposit.
    derived_address: Mapped[str] = mapped_column(String(128), nullable=False)
    derivation_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Destination treasury address.
    treasury_address: Mapped[str] = mapped_column(String(128), nullable=False)

    # USDT amount detected on chain and swept.
    gross_amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    swept_amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))

    # Gas top-up step.
    gas_topup_tx_hash: Mapped[str | None] = mapped_column(String(128))
    gas_topup_amount_bnb: Mapped[Decimal | None] = mapped_column(Numeric(18, 18))

    # USDT sweep step.
    sweep_tx_hash: Mapped[str | None] = mapped_column(String(128))

    # Dust return step (left-over BNB sent back to the gas wallet).
    dust_return_tx_hash: Mapped[str | None] = mapped_column(String(128))
    dust_return_amount_bnb: Mapped[str | None] = mapped_column(String(128))

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    error: Mapped[str | None] = mapped_column(Text)

    deposit: Mapped["Deposit"] = relationship(back_populates="bep20_sweep", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Bep20Sweep {self.derived_address} {self.status}>"


class Trc20Sweep(Base, UUIDPrimaryKeyMixin, TimestampMixin, UpdatedAtMixin):
    """Automatic consolidation of a TRC20 (TRON) USDT deposit to the treasury.

    Mirrors Bep20Sweep. Each row tracks the full lifecycle: gas top-up (in
    TRX), USDT sweep, and dust return. If any step fails the row stays in
    ``failed`` status so an operator can retry or investigate.
    """

    __tablename__ = "trc20_sweeps"
    __table_args__ = (
        Index("ix_trc20_sweeps_deposit", "deposit_id", unique=True),
        Index("ix_trc20_sweeps_status", "status"),
    )

    deposit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deposits.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Source derived address that received the USDT deposit.
    derived_address: Mapped[str] = mapped_column(String(128), nullable=False)
    derivation_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Destination treasury address.
    treasury_address: Mapped[str] = mapped_column(String(128), nullable=False)

    # USDT amount detected on chain and swept.
    gross_amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    swept_amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))

    # Gas top-up step (in TRX).
    gas_topup_tx_hash: Mapped[str | None] = mapped_column(String(128))
    gas_topup_amount_trx: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))

    # USDT sweep step.
    sweep_tx_hash: Mapped[str | None] = mapped_column(String(128))

    # Dust return step (left-over TRX sent back to the gas wallet).
    dust_return_tx_hash: Mapped[str | None] = mapped_column(String(128))
    dust_return_amount_trx: Mapped[str | None] = mapped_column(String(128))

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    error: Mapped[str | None] = mapped_column(Text)

    deposit: Mapped["Deposit"] = relationship(back_populates="trc20_sweep", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Trc20Sweep {self.derived_address} {self.status}>"


class PlatformRevenue(Base, UUIDPrimaryKeyMixin):
    """One row per billable event, splitting advertiser spend into commission.

    ``gross_amount_usd`` is what the advertiser paid; ``commission_amount_usd``
    is the platform's 35% cut; the remainder is the publisher's share.
    """

    __tablename__ = "platform_revenue"
    __table_args__ = (
        CheckConstraint("source_type IN ('campaign_spend')", name="source_type_valid"),
        CheckConstraint("gross_amount_usd >= 0", name="gross_non_negative"),
        CheckConstraint("commission_amount_usd >= 0", name="commission_non_negative"),
        Index("ix_platform_revenue_recorded", "recorded_at"),
        Index("ix_platform_revenue_source", "source_type", "source_id"),
    )

    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="campaign_spend")
    source_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    gross_amount_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    commission_amount_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    publisher_amount_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    event_type: Mapped[str | None] = mapped_column(String(24))  # impression | click
    placement_type: Mapped[str | None] = mapped_column(String(16))
    placement_id: Mapped[uuid.UUID | None] = mapped_column()
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()", index=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlatformRevenue {self.gross_amount_usd} / {self.commission_amount_usd}>"


class WalletAddress(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Cache of derived watch-only deposit addresses, one per advertiser+network.

    Derivation is deterministic, but persisting it lets the deposit watcher scan
    a plain index instead of re-deriving thousands of addresses each run.
    """

    __tablename__ = "wallet_addresses"
    __table_args__ = (
        Index("ix_wallet_addresses_unique", "advertiser_id", "network", unique=True),
        Index("ix_wallet_addresses_address", "address"),
    )

    advertiser_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("advertisers.id", ondelete="CASCADE"), nullable=False
    )
    network: Mapped[str] = mapped_column(String(8), nullable=False)
    address: Mapped[str] = mapped_column(String(128), nullable=False)
    memo: Mapped[str | None] = mapped_column(String(64), index=True)
    derivation_path: Mapped[str | None] = mapped_column(String(64))
    derivation_index: Mapped[int | None] = mapped_column(Integer)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_scanned_cursor: Mapped[str | None] = mapped_column(String(128))
