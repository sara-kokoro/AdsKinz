"""Add scheduled_posts.neighbor_checked_at.

Backs app.mtproto.neighbor_check.scan_post_neighbors: marks a post as
already compared against its channel's neighboring organic posts, so the
(rate-limited, Telegram-call-heavy) neighbor scan never re-processes it.

Revision ID: 0017_neighbor_check
Revises: 0016_channel_not_started_reminder
Create Date: 2026-09-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017_neighbor_check"
down_revision: str | Sequence[str] | None = "0016_channel_not_started_reminder"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scheduled_posts",
        sa.Column("neighbor_checked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scheduled_posts", "neighbor_checked_at")
