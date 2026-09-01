"""Fix ck_channels_status_valid: migration 0008 added 'archived' to the
mini_apps status check constraint but forgot to do the same for channels,
even though it added channels.archived_at in the same migration. Archiving
a channel currently fails with a CheckViolationError.

Revision ID: 0011_fix_channels_status_check_archived
Revises: 0010_admin_login_code
Create Date: 2026-09-01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_fix_channels_status_check_archived"
down_revision: str | Sequence[str] | None = "0010_admin_login_code"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_channels_status_valid"), "channels", type_="check")
    op.create_check_constraint(
        op.f("ck_channels_status_valid"),
        "channels",
        "status IN ('pending_moderation', 'approved_not_started', "
        "'active_building_trust', 'active', 'suspended', 'archived', 'rejected')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_channels_status_valid"), "channels", type_="check")
    op.create_check_constraint(
        op.f("ck_channels_status_valid"),
        "channels",
        "status IN ('pending_moderation', 'approved_not_started', "
        "'active_building_trust', 'active', 'suspended', 'rejected')",
    )
