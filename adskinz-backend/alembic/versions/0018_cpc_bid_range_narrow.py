"""Narrow the cpc_bid range to match AdsGram-competitive pricing.

settings.MIN_CPC_BID/MAX_CPC_BID move from 0.015-0.13 to 0.01-0.03 (default
0.01), so the DB check constraint added in 0015 must move with it or every
new campaign with a cpc_bid below 0.015 or above 0.03 will fail at the DB
layer with a bare IntegrityError, same class of bug as 0013/0015.

Revision ID: 0018_cpc_bid_range_narrow
Revises: 0017_neighbor_check
Create Date: 2026-09-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018_cpc_bid_range_narrow"
down_revision: str | Sequence[str] | None = "0017_neighbor_check"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_campaigns_cpc_bid_range"), "campaigns", type_="check")
    op.create_check_constraint(
        op.f("ck_campaigns_cpc_bid_range"),
        "campaigns",
        "cpc_bid IS NULL OR (cpc_bid >= 0.01 AND cpc_bid <= 0.03)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_campaigns_cpc_bid_range"), "campaigns", type_="check")
    op.create_check_constraint(
        op.f("ck_campaigns_cpc_bid_range"),
        "campaigns",
        "cpc_bid IS NULL OR (cpc_bid >= 0.015 AND cpc_bid <= 0.13)",
    )
