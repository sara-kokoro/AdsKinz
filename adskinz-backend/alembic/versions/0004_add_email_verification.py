"""Add email verification fields to advertisers and publishers.

Revision ID: 0004_add_email_verification
Revises: 0003_add_refresh_tokens
Create Date: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_add_email_verification"
down_revision: str | Sequence[str] | None = "0003_add_refresh_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "advertisers",
        sa.Column("email_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "advertisers",
        sa.Column("email_verification_code", sa.String(length=8)),
    )
    op.add_column(
        "advertisers",
        sa.Column("email_verification_expires_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "publishers",
        sa.Column("email_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "publishers",
        sa.Column("email_verification_code", sa.String(length=8)),
    )
    op.add_column(
        "publishers",
        sa.Column("email_verification_expires_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_column("publishers", "email_verification_expires_at")
    op.drop_column("publishers", "email_verification_code")
    op.drop_column("publishers", "email_verified")
    op.drop_column("advertisers", "email_verification_expires_at")
    op.drop_column("advertisers", "email_verification_code")
    op.drop_column("advertisers", "email_verified")
