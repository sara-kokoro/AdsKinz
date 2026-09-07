"""Align ck_campaigns_cpm_min / ck_campaigns_daily_budget_min with the actual
application floors and add a per-click bidding option.

Same class of bug as migration 0013: `app/config.py` (settings.MIN_CPM_BID)
and the Pydantic validators in `app/schemas/advertiser.py` have always
advertised and enforced a $1.70 CPM floor, but the live DB constraint still
required >= 2.00 — so any campaign created or updated with a CPM between
1.70 and 1.99 has always failed at the database layer with a generic
IntegrityError (surfaced to advertisers as a bare "AdsKinz API error"), even
though the UI and the API validators both told them 1.70 was acceptable.
Same mismatch existed for daily_budget (app floor 1.80, DB floor 2.00).

Also adds `cpc_bid`: advertisers can now bid cost-per-click instead of (or
in addition to) CPM, bounded to settings.MIN_CPC_BID..MAX_CPC_BID
($0.015-$0.13).

Revision ID: 0015_cpm_floor_and_cpc_bid
Revises: 0014_short_tracking_ids
Create Date: 2026-09-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015_cpm_floor_and_cpc_bid"
down_revision: str | Sequence[str] | None = "0014_short_tracking_ids"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_campaigns_cpm_min"), "campaigns", type_="check")
    op.create_check_constraint(op.f("ck_campaigns_cpm_min"), "campaigns", "cpm_bid >= 1.70")

    op.drop_constraint(op.f("ck_campaigns_daily_budget_min"), "campaigns", type_="check")
    op.create_check_constraint(
        op.f("ck_campaigns_daily_budget_min"),
        "campaigns",
        "daily_budget IS NULL OR daily_budget >= 1.80",
    )

    op.add_column("campaigns", sa.Column("cpc_bid", sa.Numeric(6, 3), nullable=True))
    op.create_check_constraint(
        op.f("ck_campaigns_cpc_bid_range"),
        "campaigns",
        "cpc_bid IS NULL OR (cpc_bid >= 0.015 AND cpc_bid <= 0.13)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_campaigns_cpc_bid_range"), "campaigns", type_="check")
    op.drop_column("campaigns", "cpc_bid")

    op.drop_constraint(op.f("ck_campaigns_daily_budget_min"), "campaigns", type_="check")
    op.create_check_constraint(
        op.f("ck_campaigns_daily_budget_min"),
        "campaigns",
        "daily_budget IS NULL OR daily_budget >= 2.00",
    )

    op.drop_constraint(op.f("ck_campaigns_cpm_min"), "campaigns", type_="check")
    op.create_check_constraint(op.f("ck_campaigns_cpm_min"), "campaigns", "cpm_bid >= 2.00")
