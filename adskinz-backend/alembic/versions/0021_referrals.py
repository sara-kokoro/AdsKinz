"""Referral program.

- Publishers: a referring publisher earns REFERRAL_PUBLISHER_RATE (3%) of
  every earning their referred publisher gets (channel/mini-app payouts).
- Advertisers: a referring advertiser earns REFERRAL_ADVERTISER_RATE (5%)
  of every confirmed deposit their referred advertiser makes.

Both tables get the same two columns: a unique, shareable referral_code,
and referred_by_id pointing at the account (same table) that referred them.
Self-referential FK, nullable, ON DELETE SET NULL so deleting a referrer
never cascades into their referrals.

Revision ID: 0021_referrals
Revises: 0020_advertiser_premium
Create Date: 2026-09-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0021_referrals"
down_revision: str | Sequence[str] | None = "0020_advertiser_premium"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("advertisers", "publishers"):
        op.add_column(table, sa.Column("referral_code", sa.String(length=16), nullable=True))
        op.add_column(
            table,
            sa.Column("referred_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_index(f"ix_{table}_referral_code", table, ["referral_code"], unique=True)
        op.create_foreign_key(
            f"fk_{table}_referred_by_id",
            table,
            table,
            ["referred_by_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for table in ("advertisers", "publishers"):
        op.drop_constraint(f"fk_{table}_referred_by_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_referral_code", table_name=table)
        op.drop_column(table, "referred_by_id")
        op.drop_column(table, "referral_code")
