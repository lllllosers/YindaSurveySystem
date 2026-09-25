"""add result preflight review and central records

Revision ID: 20260925_0207
Revises: 20260925_0206
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260925_0207"
down_revision: str | None = "20260925_0206"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("result_submissions", sa.Column("submission_task_uid", sa.String(32), nullable=True))
    op.add_column("result_submissions", sa.Column("preflight_error_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("result_submissions", sa.Column("preflight_warning_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("result_submissions", sa.Column("preflight_issues_json", sa.JSON(), nullable=True))
    op.add_column("result_submissions", sa.Column("preflight_summary_json", sa.JSON(), nullable=True))
    op.add_column("result_submissions", sa.Column("preflight_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("result_submissions", sa.Column("review_notes", sa.Text(), nullable=True))
    op.add_column("result_submissions", sa.Column("reviewed_by_user_uid", sa.String(32), nullable=True))
    op.add_column("result_submissions", sa.Column("reviewed_by_username", sa.String(80), nullable=True))
    op.add_column("result_submissions", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("result_submissions", sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_result_submissions_submission_task_uid", "result_submissions", ["submission_task_uid"])
    op.create_index("ix_result_submissions_reviewed_by_user_uid", "result_submissions", ["reviewed_by_user_uid"])
    op.create_check_constraint(
        "ck_result_submissions_preflight_counts",
        "result_submissions",
        "preflight_error_count >= 0 AND preflight_warning_count >= 0",
    )
    op.drop_constraint("ck_result_submissions_status", "result_submissions", type_="check")
    op.create_check_constraint(
        "ck_result_submissions_status",
        "result_submissions",
        "status IN ('uploaded','inspected','invalid','preflight_passed','conflict','reviewing','accepted','rejected','imported')",
    )

    op.create_table(
        "central_engineering_assets",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("engineering_asset_uid", sa.String(32), nullable=False),
        sa.Column("project_uid", sa.String(32), nullable=False),
        sa.Column("asset_name", sa.String(300), nullable=True),
        sa.Column("asset_type", sa.String(100), nullable=True),
        sa.Column("organization_unit_uid", sa.String(32), nullable=True),
        sa.Column("canal_unit_uid", sa.String(32), nullable=True),
        sa.Column("business_code", sa.String(160), nullable=True),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("current_submission_uid", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("engineering_asset_uid"),
    )
    op.create_table(
        "central_survey_records",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("survey_record_uid", sa.String(32), nullable=False),
        sa.Column("engineering_asset_uid", sa.String(32), nullable=False),
        sa.Column("project_uid", sa.String(32), nullable=False),
        sa.Column("survey_batch_uid", sa.String(32), nullable=False),
        sa.Column("form_code", sa.String(80), nullable=False),
        sa.Column("organization_unit_uid", sa.String(32), nullable=False),
        sa.Column("canal_unit_uid", sa.String(32), nullable=False),
        sa.Column("source_task_uid", sa.String(32), nullable=True),
        sa.Column("source_management_scope_uid", sa.String(32), nullable=True),
        sa.Column("record_status", sa.String(30), nullable=True),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("current_submission_uid", sa.String(32), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("survey_record_uid"),
    )
    op.create_table(
        "central_inspection_results",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("survey_record_uid", sa.String(32), nullable=False),
        sa.Column("item_code", sa.String(100), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("current_submission_uid", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("survey_record_uid", "item_code", name="uq_central_inspection_record_item"),
    )
    op.create_table(
        "central_survey_media",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("media_uid", sa.String(32), nullable=False),
        sa.Column("survey_record_uid", sa.String(32), nullable=False),
        sa.Column("package_path", sa.String(600), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("current_submission_uid", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("media_uid"),
    )
    indexes = {
        "central_engineering_assets": ["project_uid", "asset_type", "organization_unit_uid", "canal_unit_uid", "business_code", "current_submission_uid"],
        "central_survey_records": ["engineering_asset_uid", "project_uid", "survey_batch_uid", "form_code", "organization_unit_uid", "canal_unit_uid", "source_task_uid", "source_management_scope_uid", "record_status", "current_submission_uid"],
        "central_inspection_results": ["survey_record_uid", "current_submission_uid"],
        "central_survey_media": ["survey_record_uid", "current_submission_uid"],
    }
    for table, columns in indexes.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    op.drop_table("central_survey_media")
    op.drop_table("central_inspection_results")
    op.drop_table("central_survey_records")
    op.drop_table("central_engineering_assets")
    op.drop_constraint("ck_result_submissions_status", "result_submissions", type_="check")
    op.drop_constraint("ck_result_submissions_preflight_counts", "result_submissions", type_="check")
    op.create_check_constraint(
        "ck_result_submissions_status",
        "result_submissions",
        "status IN ('uploaded','inspected','invalid','preflight_passed','conflict','reviewing','accepted','rejected')",
    )
    op.drop_index("ix_result_submissions_reviewed_by_user_uid", table_name="result_submissions")
    op.drop_index("ix_result_submissions_submission_task_uid", table_name="result_submissions")
    for column in (
        "imported_at", "reviewed_at", "reviewed_by_username", "reviewed_by_user_uid",
        "review_notes", "preflight_checked_at", "preflight_summary_json",
        "preflight_issues_json", "preflight_warning_count", "preflight_error_count",
        "submission_task_uid",
    ):
        op.drop_column("result_submissions", column)
