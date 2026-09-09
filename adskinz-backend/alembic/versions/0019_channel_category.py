"""Add channel category auto-detection.

Adds ``category`` (one of app.core.enums.CHANNEL_CATEGORIES, enforced at the
Pydantic layer, not a DB check constraint, so the allowed list can evolve
without a migration) and ``category_source`` ("manual" | "keywords" | "ai")
to ``channels``.

Revision ID: 0019_channel_category
Revises: 0018_cpc_bid_range_narrow
Create Date: 2026-09-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019_channel_category"
down_revision: str | Sequence[str] | None = "0018_cpc_bid_range_narrow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("channels", sa.Column("category", sa.String(length=32), nullable=True))
    op.add_column("channels", sa.Column("category_source", sa.String(length=16), nullable=True))
    op.create_index("ix_channels_category", "channels", ["category"])


def downgrade() -> None:
    op.drop_index("ix_channels_category", table_name="channels")
    op.drop_column("channels", "category_source")
    op.drop_column("channels", "category")
