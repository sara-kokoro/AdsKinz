"""Add channels.not_started_reminder_sent_at.

Backs the new `remind_unstarted_channels` job: a channel that gets approved
by moderation but whose publisher never presses Start sits invisible to
advertisers forever (it never enters the eligible-channel pool — see
app/services/ad_selection_service.eligible_channels). With no reminder, an
idle approval is easy to simply forget about. This column lets the job send
exactly one nudge email per approval instead of re-sending every run.

Revision ID: 0016_channel_not_started_reminder
Revises: 0015_cpm_floor_and_cpc_bid
Create Date: 2026-09-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016_channel_not_started_reminder"
down_revision: str | Sequence[str] | None = "0015_cpm_floor_and_cpc_bid"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("not_started_reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channels", "not_started_reminder_sent_at")
