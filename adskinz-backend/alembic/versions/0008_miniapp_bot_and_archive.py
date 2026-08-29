"""Add bot_username/bot_token to mini_apps, allow 'archived' status on
channels and mini_apps (suspend/archive instead of delete).

Revision ID: 0008_miniapp_bot_and_archive
Revises: 0007_channel_logo_subs_refresh
Create Date: 2026-08-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008_miniapp_bot_and_archive"
down_revision: str | Sequence[str] | None = "0007_channel_logo_subs_refresh"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mini_apps", sa.Column("bot_username", sa.String(length=64), nullable=True))
    # bot_token is sensitive (used only server-side to validate Telegram's
    # WebApp initData signature) — never returned in any API response.
    op.add_column("mini_apps", sa.Column("bot_token", sa.Text(), nullable=True))
    op.add_column(
        "mini_apps", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("channels", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    op.drop_constraint("status_valid", "mini_apps", type_="check")
    op.create_check_constraint(
        "status_valid",
        "mini_apps",
        "status IN ('pending_moderation', 'active', 'suspended', 'archived', 'rejected')",
    )


def downgrade() -> None:
    op.drop_constraint("status_valid", "mini_apps", type_="check")
    op.create_check_constraint(
        "status_valid",
        "mini_apps",
        "status IN ('pending_moderation', 'active', 'suspended', 'rejected')",
    )
    op.drop_column("channels", "archived_at")
    op.drop_column("mini_apps", "archived_at")
    op.drop_column("mini_apps", "bot_token")
    op.drop_column("mini_apps", "bot_username")
