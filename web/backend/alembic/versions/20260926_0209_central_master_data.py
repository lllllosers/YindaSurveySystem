"""add centrally managed master data

Revision ID: 20260926_0209
Revises: 20260926_0208
Create Date: 2026-09-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260926_0209"
down_revision: str | None = "20260926_0208"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "master_data_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("base_version", sa.String(120), nullable=False),
        sa.Column("source_description", sa.Text(), nullable=False),
        sa.Column("updated_by_username", sa.String(80), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("revision_no >= 1", name="ck_master_data_state_revision"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "master_departments",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("stable_uid", sa.String(32), nullable=False),
        sa.Column("master_key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("business_code", sa.String(40), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_master_departments_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stable_uid"),
        sa.UniqueConstraint("master_key"),
        sa.UniqueConstraint("business_code"),
    )
    op.create_table(
        "master_offices",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("stable_uid", sa.String(32), nullable=False),
        sa.Column("master_key", sa.String(100), nullable=False),
        sa.Column("parent_department_uid", sa.String(32), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("business_code", sa.String(40), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_master_offices_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stable_uid"),
        sa.UniqueConstraint("master_key"),
        sa.UniqueConstraint("parent_department_uid", "business_code", name="uq_master_office_parent_code"),
    )
    op.create_index("ix_master_offices_parent_department_uid", "master_offices", ["parent_department_uid"])
    op.create_table(
        "master_canals",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("stable_uid", sa.String(32), nullable=False),
        sa.Column("master_key", sa.String(100), nullable=False),
        sa.Column("parent_canal_uid", sa.String(32), nullable=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("canal_level", sa.String(10), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_master_canals_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stable_uid"),
        sa.UniqueConstraint("master_key"),
    )
    op.create_index("ix_master_canals_parent_canal_uid", "master_canals", ["parent_canal_uid"])
    op.create_table(
        "master_management_scopes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("stable_uid", sa.String(32), nullable=False),
        sa.Column("master_key", sa.String(140), nullable=False),
        sa.Column("canal_uid", sa.String(32), nullable=False),
        sa.Column("organization_unit_uid", sa.String(32), nullable=False),
        sa.Column("range_mode", sa.String(30), nullable=False),
        sa.Column("start_stake_text", sa.String(40), nullable=True),
        sa.Column("start_stake_value", sa.Float(), nullable=True),
        sa.Column("end_stake_text", sa.String(40), nullable=True),
        sa.Column("end_stake_value", sa.Float(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_master_management_scopes_status"),
        sa.CheckConstraint("range_mode IN ('whole','segment_known','segment_unknown')", name="ck_master_management_scopes_range_mode"),
        sa.CheckConstraint("(range_mode = 'segment_known' AND start_stake_value IS NOT NULL AND end_stake_value IS NOT NULL AND start_stake_value <= end_stake_value) OR (range_mode IN ('whole','segment_unknown') AND start_stake_text IS NULL AND start_stake_value IS NULL AND end_stake_text IS NULL AND end_stake_value IS NULL)", name="ck_master_management_scopes_range_values"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stable_uid"),
        sa.UniqueConstraint("master_key"),
    )
    op.create_index("ix_master_management_scopes_canal_uid", "master_management_scopes", ["canal_uid"])
    op.create_index("ix_master_management_scopes_organization_unit_uid", "master_management_scopes", ["organization_unit_uid"])


def downgrade() -> None:
    op.drop_table("master_management_scopes")
    op.drop_table("master_canals")
    op.drop_table("master_offices")
    op.drop_table("master_departments")
    op.drop_table("master_data_state")
