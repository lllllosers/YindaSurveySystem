"""add web survey task issuance history

Revision ID: 20260925_0206
Revises: 20260918_0205
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260925_0206"
down_revision: str | None = "20260918_0205"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "survey_tasks",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("task_uid", sa.String(32), nullable=False),
        sa.Column("package_uid", sa.String(32), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("survey_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("task_name", sa.String(240), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("target_unit_type", sa.String(30), nullable=False),
        sa.Column("department_uid", sa.String(32), nullable=False),
        sa.Column("department_name", sa.String(160), nullable=False),
        sa.Column("organization_unit_uid", sa.String(32), nullable=False),
        sa.Column("organization_name", sa.String(160), nullable=False),
        sa.Column("parent_task_uid", sa.String(32), nullable=True),
        sa.Column("root_task_uid", sa.String(32), nullable=False),
        sa.Column("task_depth", sa.Integer(), nullable=False),
        sa.Column("selected_scope_uids", sa.JSON(), nullable=False),
        sa.Column("frozen_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("selected_scope_count", sa.Integer(), nullable=False),
        sa.Column("reference_canal_count", sa.Integer(), nullable=False),
        sa.Column("reference_organization_count", sa.Integer(), nullable=False),
        sa.Column("form_count", sa.Integer(), nullable=False),
        sa.Column("stored_relative_path", sa.String(600), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(30), server_default="issued", nullable=False),
        sa.Column("download_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("first_downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_uid", sa.String(32), nullable=False),
        sa.Column("created_by_username", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("target_unit_type IN ('department','water_office')", name="ck_survey_tasks_target_unit_type"),
        sa.CheckConstraint("status IN ('issued','downloaded','result_received','closed','cancelled')", name="ck_survey_tasks_status"),
        sa.CheckConstraint("task_depth >= 0", name="ck_survey_tasks_depth"),
        sa.CheckConstraint("selected_scope_count > 0", name="ck_survey_tasks_scope_count"),
        sa.CheckConstraint("file_size >= 0", name="ck_survey_tasks_file_size"),
        sa.CheckConstraint("download_count >= 0", name="ck_survey_tasks_download_count"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["survey_batch_id"], ["survey_batches.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_uid"),
        sa.UniqueConstraint("package_uid"),
        sa.UniqueConstraint("stored_relative_path"),
    )
    for column in (
        "project_id", "survey_batch_id", "department_uid", "organization_unit_uid",
        "parent_task_uid", "root_task_uid", "file_sha256", "status",
        "created_by_user_uid", "created_at",
    ):
        op.create_index(f"ix_survey_tasks_{column}", "survey_tasks", [column], unique=False)


def downgrade() -> None:
    op.drop_table("survey_tasks")
