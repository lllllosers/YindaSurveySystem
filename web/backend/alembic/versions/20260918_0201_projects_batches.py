"""create projects and survey batches

Revision ID: 20260918_0201
Revises:
Create Date: 2026-09-18
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260918_0201"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("project_uid", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("short_name", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_projects_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_uid",
            name="uq_projects_project_uid",
        ),
    )

    op.create_table(
        "survey_batches",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("survey_batch_uid", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_name", sa.String(length=200), nullable=False),
        sa.Column("batch_code", sa.String(length=50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="planned",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'active', 'closed')",
            name="ck_survey_batches_status",
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_survey_batches_date_range",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "survey_batch_uid",
            name="uq_survey_batches_uid",
        ),
        sa.UniqueConstraint(
            "project_id",
            "batch_code",
            name="uq_survey_batches_project_code",
        ),
    )
    op.create_index(
        "ix_survey_batches_project_id",
        "survey_batches",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_survey_batches_project_id",
        table_name="survey_batches",
    )
    op.drop_table("survey_batches")
    op.drop_table("projects")
