"""Merge divergent heads (publisher premium / referrals).

Revision ID: 0022_merge_premium_heads
Revises: 0020_publisher_premium, 0021_referrals
Create Date: 2026-09-09
"""

from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0022_merge_premium_heads"
down_revision: str | Sequence[str] | None = ("0020_publisher_premium", "0021_referrals")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
