"""add online survey entries

Revision ID: 20260926_0208
Revises: 20260925_0207
Create Date: 2026-09-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260926_0208"
down_revision: str | None = "20260925_0207"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "online_survey_entries",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("entry_uid", sa.String(32), nullable=False),
        sa.Column("task_uid", sa.String(32), nullable=False),
        sa.Column("project_uid", sa.String(32), nullable=False),
        sa.Column("survey_batch_uid", sa.String(32), nullable=False),
        sa.Column("management_scope_uid", sa.String(32), nullable=False),
        sa.Column("organization_unit_uid", sa.String(32), nullable=False),
        sa.Column("organization_name", sa.String(160), nullable=False),
        sa.Column("canal_unit_uid", sa.String(32), nullable=False),
        sa.Column("canal_name", sa.String(160), nullable=False),
        sa.Column("form_code", sa.String(80), nullable=False),
        sa.Column("form_name", sa.String(240), nullable=False),
        sa.Column("asset_name", sa.String(300), nullable=True),
        sa.Column("form_data_json", sa.JSON(), nullable=False),
        sa.Column("evaluations_json", sa.JSON(), nullable=False),
        sa.Column("conclusion_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), server_default="draft", nullable=False),
        sa.Column("revision_no", sa.Integer(), server_default="1", nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_uid", sa.String(32), nullable=False),
        sa.Column("created_by_username", sa.String(80), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_uid", sa.String(32), nullable=True),
        sa.Column("reviewed_by_username", sa.String(80), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft','submitted','accepted','rejected','imported')",
            name="ck_online_survey_entries_status",
        ),
        sa.CheckConstraint("revision_no >= 1", name="ck_online_survey_entries_revision"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_uid"),
    )
    for column in (
        "task_uid", "project_uid", "survey_batch_uid", "management_scope_uid",
        "organization_unit_uid", "canal_unit_uid", "form_code", "asset_name", "status",
        "created_by_user_uid", "reviewed_by_user_uid", "created_at",
    ):
        op.create_index(f"ix_online_survey_entries_{column}", "online_survey_entries", [column])


def downgrade() -> None:
    op.drop_table("online_survey_entries")
