"""add result storage verification state

Revision ID: 20260918_0205
Revises: 20260918_0204
Create Date: 2026-09-18
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260918_0205"
down_revision: str | None = "20260918_0204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "result_submissions",
        sa.Column(
            "storage_status",
            sa.String(length=30),
            server_default="unchecked",
            nullable=False,
        ),
    )
    op.add_column(
        "result_submissions",
        sa.Column(
            "storage_checked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "result_submissions",
        sa.Column(
            "storage_check_json",
            sa.JSON(),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_result_submissions_storage_status",
        "result_submissions",
        (
            "storage_status IN ("
            "'unchecked','ok','missing','size_mismatch',"
            "'hash_mismatch','package_invalid','error'"
            ")"
        ),
    )
    op.create_index(
        "ix_result_submissions_storage_status",
        "result_submissions",
        ["storage_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_result_submissions_storage_status",
        table_name="result_submissions",
    )
    op.drop_constraint(
        "ck_result_submissions_storage_status",
        "result_submissions",
        type_="check",
    )
    op.drop_column(
        "result_submissions",
        "storage_check_json",
    )
    op.drop_column(
        "result_submissions",
        "storage_checked_at",
    )
    op.drop_column(
        "result_submissions",
        "storage_status",
    )
