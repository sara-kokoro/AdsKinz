"""Relay deposits — suivi des dépôts JessiKaPay relayés via pay.adskinz.me.

Table indépendante de la facturation adskinz (Deposit/LedgerEntry) : sert
uniquement de journal de suivi pour le relais MoneyFusion vers JessiKaPay.

Revision ID: 0023_relay_deposits
Revises: 0022_merge_premium_heads
Create Date: 2026-09-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_relay_deposits"
down_revision: str | Sequence[str] | None = "0022_merge_premium_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "relay_deposits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("jkpay_tx_id", sa.String(length=64), nullable=False),
        sa.Column("tgid", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("operator", sa.String(length=64), nullable=False),
        sa.Column("country", sa.String(length=8), nullable=False),
        sa.Column("moneyfusion_token", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("jkpay_notified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("jkpay_notify_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_relay_deposits_jkpay_tx_id", "relay_deposits", ["jkpay_tx_id"], unique=True)
    op.create_index("ix_relay_deposits_tgid", "relay_deposits", ["tgid"])
    op.create_index("ix_relay_deposits_moneyfusion_token", "relay_deposits", ["moneyfusion_token"])
    op.create_index("ix_relay_deposits_status", "relay_deposits", ["status"])


def downgrade() -> None:
    op.drop_table("relay_deposits")
