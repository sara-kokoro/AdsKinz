"""Add TRC20 sweep tracking table.

Revision ID: 0004_add_trc20_sweeps
Revises: 0003_add_refresh_tokens
Create Date: 2026-08-21
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_add_trc20_sweeps"
down_revision: str | Sequence[str] | None = "0003_add_refresh_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trc20_sweeps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "deposit_id",
            sa.UUID(),
            sa.ForeignKey("deposits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("derived_address", sa.String(length=128), nullable=False),
        sa.Column("derivation_index", sa.Integer(), nullable=False),
        sa.Column("treasury_address", sa.String(length=128), nullable=False),
        sa.Column("gross_amount_usd", sa.Numeric(precision=12, scale=6)),
        sa.Column("swept_amount_usd", sa.Numeric(precision=12, scale=6)),
        sa.Column("gas_topup_tx_hash", sa.String(length=128)),
        sa.Column("gas_topup_amount_trx", sa.Numeric(precision=18, scale=6)),
        sa.Column("sweep_tx_hash", sa.String(length=128)),
        sa.Column("dust_return_tx_hash", sa.String(length=128)),
        sa.Column("dust_return_amount_trx", sa.String(length=128)),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trc20_sweeps")),
        sa.UniqueConstraint("deposit_id", name=op.f("uq_trc20_sweeps_deposit_id")),
    )
    op.create_index("ix_trc20_sweeps_deposit", "trc20_sweeps", ["deposit_id"], unique=True)
    op.create_index("ix_trc20_sweeps_status", "trc20_sweeps", ["status"])


def downgrade() -> None:
    op.drop_index("ix_trc20_sweeps_status", table_name="trc20_sweeps")
    op.drop_index("ix_trc20_sweeps_deposit", table_name="trc20_sweeps")
    op.drop_table("trc20_sweeps")
