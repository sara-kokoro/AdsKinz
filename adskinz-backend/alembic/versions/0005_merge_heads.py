"""Merge divergent heads (email verification / TRC20 sweeps).

Revision ID: 0005_merge_heads
Revises: 0004_add_email_verification, 0004_add_trc20_sweeps
Create Date: 2026-08-25
"""

from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0005_merge_heads"
down_revision: str | Sequence[str] | None = ("0004_add_email_verification", "0004_add_trc20_sweeps")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
