"""Add the 8-digit email sign-in code fields to admin_users and make
totp_secret nullable (the old TOTP-based login is replaced by an emailed
code + a fixed console password).

Revision ID: 0010_admin_login_code
Revises: 0009_channel_weekly_slots
Create Date: 2026-08-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0010_admin_login_code"
down_revision: str | Sequence[str] | None = "0009_channel_weekly_slots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("admin_users", sa.Column("login_code_hash", sa.Text(), nullable=True))
    op.add_column(
        "admin_users", sa.Column("login_code_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.alter_column("admin_users", "totp_secret", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("admin_users", "totp_secret", existing_type=sa.Text(), nullable=False)
    op.drop_column("admin_users", "login_code_expires_at")
    op.drop_column("admin_users", "login_code_hash")
