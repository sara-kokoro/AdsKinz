"""Publisher premium tier (poster/creative generation, $9.99/mo).

Charged against the publisher's existing available_balance_usd (see
billing_service.charge_premium) — no separate deposit/payment rail.

Revision ID: 0020_publisher_premium
Revises: 0019_channel_category
Create Date: 2026-09-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020_publisher_premium"
down_revision: str | Sequence[str] | None = "0019_channel_category"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "publishers",
        sa.Column("is_premium", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "publishers", sa.Column("premium_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "publishers",
        sa.Column("premium_auto_renew", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_publishers_is_premium", "publishers", ["is_premium"])


def downgrade() -> None:
    op.drop_index("ix_publishers_is_premium", table_name="publishers")
    op.drop_column("publishers", "premium_auto_renew")
    op.drop_column("publishers", "premium_expires_at")
    op.drop_column("publishers", "is_premium")
