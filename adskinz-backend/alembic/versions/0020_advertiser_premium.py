"""Advertiser premium tier (AI poster/creative generation, $9.99/mo).

Charged against the advertiser's existing balance_usd (see
billing_service.charge_premium) — no separate deposit/payment rail.

Note: this is for advertisers, not publishers — advertisers are the ones
who need ad posters generated for their campaigns.

Revision ID: 0020_advertiser_premium
Revises: 0019_channel_category
Create Date: 2026-09-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020_advertiser_premium"
down_revision: str | Sequence[str] | None = "0019_channel_category"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "advertisers",
        sa.Column("is_premium", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "advertisers", sa.Column("premium_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "advertisers",
        sa.Column("premium_auto_renew", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_advertisers_is_premium", "advertisers", ["is_premium"])


def downgrade() -> None:
    op.drop_index("ix_advertisers_is_premium", table_name="advertisers")
    op.drop_column("advertisers", "premium_auto_renew")
    op.drop_column("advertisers", "premium_expires_at")
    op.drop_column("advertisers", "is_premium")
