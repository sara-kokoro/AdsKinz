"""Lower the campaign minimum budget from $50 to $20, and add a
low_balance_alerted_at column so we can email advertisers once per campaign
when its remaining budget drops under the low-balance threshold (currently
$5), instead of only alerting on overall wallet balance.

Revision ID: 0012_campaign_min_budget
Revises: 0011_fix_channels_archived
Create Date: 2026-09-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
# NOTE: keep this id <= 32 chars -- it's stored in alembic_version.version_num,
# which is a VARCHAR(32) column.
revision: str = "0012_campaign_min_budget"
down_revision: str | Sequence[str] | None = "0011_fix_channels_archived"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_campaigns_budget_min"), "campaigns", type_="check")
    op.create_check_constraint(
        op.f("ck_campaigns_budget_min"), "campaigns", "total_budget >= 20.00"
    )
    op.add_column(
        "campaigns",
        sa.Column("low_balance_alerted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("campaigns", "low_balance_alerted_at")
    op.drop_constraint(op.f("ck_campaigns_budget_min"), "campaigns", type_="check")
    op.create_check_constraint(
        op.f("ck_campaigns_budget_min"), "campaigns", "total_budget >= 50.00"
    )
