"""Switch tracking_id from a UUID to a short alphanumeric code.

Tracking links move from https://adskinz.me/t/{uuid} to
https://tr.adskinz.me/+{13-char-code} (see core.security.generate_tracking_id
and config.Settings.tracking_link). The four tables that carry a tracking_id
(scheduled_posts, impressions, clicks, tracking_links) switch their column
from the native `uuid` type to `varchar(36)` — wide enough for the new
13-character codes while still holding any UUID already stored, so existing
rows are preserved as text rather than dropped.

Revision ID: 0014_short_tracking_ids
Revises: 0013_campaign_zero_budget
Create Date: 2026-09-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
# NOTE: keep this id <= 32 chars -- it's stored in alembic_version.version_num,
# which is a VARCHAR(32) column.
revision: str = "0014_short_tracking_ids"
down_revision: str | Sequence[str] | None = "0013_campaign_zero_budget"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = [
    ("scheduled_posts", "tracking_id", True),
    ("impressions", "tracking_id", False),
    ("clicks", "tracking_id", False),
    ("tracking_links", "tracking_id", False),
]


def upgrade() -> None:
    for table, column, nullable in _COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.String(length=36),
            existing_type=postgresql.UUID(as_uuid=True),
            postgresql_using=f"{column}::text",
            existing_nullable=nullable,
        )


def downgrade() -> None:
    # Lossy if any row already holds a new-style 13-char code (it does not
    # cast to uuid). Only safe to run before the first short id is issued.
    for table, column, nullable in _COLUMNS:
        op.alter_column(
            table,
            column,
            type_=postgresql.UUID(as_uuid=True),
            existing_type=sa.String(length=36),
            postgresql_using=f"{column}::uuid",
            existing_nullable=nullable,
        )
