"""add online entry media metadata

Revision ID: 20260926_0210
Revises: 20260926_0209
Create Date: 2026-09-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260926_0210"
down_revision: str | None = "20260926_0209"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "online_survey_entries",
        sa.Column(
            "media_json",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("online_survey_entries", "media_json")
