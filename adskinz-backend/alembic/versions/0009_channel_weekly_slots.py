"""Replace channels.preferred_hours_utc (flat hour list) with
preferred_slots (JSONB, per-weekday hour lists) so publishers can set a
different posting schedule for each day of the week.

Revision ID: 0009_channel_weekly_slots
Revises: 0008_miniapp_bot_and_archive
Create Date: 2026-08-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0009_channel_weekly_slots"
down_revision: str | Sequence[str] | None = "0008_miniapp_bot_and_archive"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def upgrade() -> None:
    op.add_column("channels", sa.Column("preferred_slots", postgresql.JSONB(), nullable=True))

    # Backfill: a channel that had the same hours every day keeps exactly
    # that behaviour under the new per-weekday shape.
    conn = op.get_bind()
    day_keys = ", ".join(f"'{d}'" for d in _DAYS)
    conn.execute(
        sa.text(
            f"""
            UPDATE channels
            SET preferred_slots = (
                SELECT jsonb_object_agg(day, to_jsonb(preferred_hours_utc))
                FROM unnest(ARRAY[{day_keys}]) AS day
            )
            WHERE preferred_hours_utc IS NOT NULL
            """
        )
    )

    op.drop_column("channels", "preferred_hours_utc")


def downgrade() -> None:
    op.add_column(
        "channels", sa.Column("preferred_hours_utc", postgresql.ARRAY(sa.Integer()), nullable=True)
    )
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE channels
            SET preferred_hours_utc = (
                SELECT array_agg(DISTINCT h::int)
                FROM jsonb_each(preferred_slots) AS d(day, hours),
                     jsonb_array_elements(hours) AS h
            )
            WHERE preferred_slots IS NOT NULL
            """
        )
    )
    op.drop_column("channels", "preferred_slots")
