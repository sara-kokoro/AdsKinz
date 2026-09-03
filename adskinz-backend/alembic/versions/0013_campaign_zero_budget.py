"""Align ck_campaigns_budget_min with the "isolated $0-start budget" model
actually implemented in app/models/campaigns.py and app/routers/advertiser.py
(create_campaign inserts total_budget=Decimal("0.00") and funding happens
afterwards through the top-up / add_budget flow). Migration 0012 lowered the
floor from $50 to $20, but never all the way to the $0 the application code
already assumes — so every campaign creation has been failing in production
with ck_campaigns_budget_min ever since, since the live constraint (>= 20.00)
never matched what the app actually inserts (0.00).

Revision ID: 0013_campaign_zero_budget
Revises: 0012_campaign_min_budget
Create Date: 2026-09-02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
# NOTE: keep this id <= 32 chars -- it's stored in alembic_version.version_num,
# which is a VARCHAR(32) column.
revision: str = "0013_campaign_zero_budget"
down_revision: str | Sequence[str] | None = "0012_campaign_min_budget"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_campaigns_budget_min"), "campaigns", type_="check")
    op.create_check_constraint(
        op.f("ck_campaigns_budget_min"), "campaigns", "total_budget >= 0.00"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_campaigns_budget_min"), "campaigns", type_="check")
    op.create_check_constraint(
        op.f("ck_campaigns_budget_min"), "campaigns", "total_budget >= 20.00"
    )
