"""Add logo_url and subscriber_count_updated_at to channels.

Revision ID: 0007_add_channel_logo_and_subscriber_refresh
Revises: 0006_add_campaign_banner_fields
Create Date: 2026-08-27
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0007_add_channel_logo_and_subscriber_refresh"
down_revision: str | Sequence[str] | None = "0006_add_campaign_banner_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("channels", sa.Column("logo_url", sa.Text(), nullable=True))
    op.add_column(
        "channels",
        sa.Column("subscriber_count_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channels", "subscriber_count_updated_at")
    op.drop_column("channels", "logo_url")
