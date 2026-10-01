"""add pending approval state for self-registered users

Revision ID: 20260927_0211
Revises: 20260926_0210
Create Date: 2026-09-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260927_0211"
down_revision: str | None = "20260926_0210"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_approved",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_approved")
