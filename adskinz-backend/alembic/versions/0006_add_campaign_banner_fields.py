"""Add title and brand_name to campaigns (separate banner fields).

Revision ID: 0006_add_campaign_banner_fields
Revises: 0005_merge_heads
Create Date: 2026-08-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006_add_campaign_banner_fields"
down_revision: str | Sequence[str] | None = "0005_merge_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("title", sa.String(length=56), nullable=True))
    op.add_column("campaigns", sa.Column("brand_name", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("campaigns", "brand_name")
    op.drop_column("campaigns", "title")
