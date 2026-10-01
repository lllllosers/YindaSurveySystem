"""add result submission intake

Revision ID: 20260918_0204
Revises: 20260918_0203
Create Date: 2026-09-18
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa


revision: str = "20260918_0204"
down_revision: str | None = "20260918_0203"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "result_submissions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("submission_uid", sa.String(32), nullable=False),
        sa.Column("package_uid", sa.String(32), nullable=True),
        sa.Column("result_uid", sa.String(32), nullable=True),
        sa.Column("project_uid", sa.String(32), nullable=True),
        sa.Column("survey_batch_uid", sa.String(32), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_relative_path", sa.String(600), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("package_format_version", sa.String(30), nullable=True),
        sa.Column("desktop_app_version", sa.String(50), nullable=True),
        sa.Column("desktop_app_version_label", sa.String(100), nullable=True),
        sa.Column("result_name", sa.String(255), nullable=True),
        sa.Column("source_task_uids", sa.JSON(), nullable=True),
        sa.Column("counts_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(30), server_default="uploaded", nullable=False),
        sa.Column("inspection_error_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("inspection_issues_json", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("uploader_user_uid", sa.String(32), nullable=False),
        sa.Column("uploader_username", sa.String(80), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("file_size >= 0", name="ck_result_submissions_file_size"),
        sa.CheckConstraint("inspection_error_count >= 0", name="ck_result_submissions_error_count"),
        sa.CheckConstraint(
            "status IN ('uploaded','inspected','invalid','preflight_passed','conflict','reviewing','accepted','rejected')",
            name="ck_result_submissions_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_uid"),
        sa.UniqueConstraint("package_uid"),
        sa.UniqueConstraint("result_uid"),
        sa.UniqueConstraint("stored_relative_path"),
    )
    op.create_index("ix_result_submissions_project_uid", "result_submissions", ["project_uid"])
    op.create_index("ix_result_submissions_survey_batch_uid", "result_submissions", ["survey_batch_uid"])
    op.create_index("ix_result_submissions_file_sha256", "result_submissions", ["file_sha256"])
    op.create_index("ix_result_submissions_status", "result_submissions", ["status"])
    op.create_index("ix_result_submissions_uploader_user_uid", "result_submissions", ["uploader_user_uid"])
    op.create_index("ix_result_submissions_uploaded_at", "result_submissions", ["uploaded_at"])


def downgrade() -> None:
    op.drop_index("ix_result_submissions_uploaded_at", table_name="result_submissions")
    op.drop_index("ix_result_submissions_uploader_user_uid", table_name="result_submissions")
    op.drop_index("ix_result_submissions_status", table_name="result_submissions")
    op.drop_index("ix_result_submissions_file_sha256", table_name="result_submissions")
    op.drop_index("ix_result_submissions_survey_batch_uid", table_name="result_submissions")
    op.drop_index("ix_result_submissions_project_uid", table_name="result_submissions")
    op.drop_table("result_submissions")
