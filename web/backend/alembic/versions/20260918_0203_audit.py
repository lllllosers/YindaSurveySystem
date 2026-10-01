"""add append-only audit events

Revision ID: 20260918_0203
Revises: 20260918_0202
Create Date: 2026-09-18
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260918_0203"
down_revision: str | None = "20260918_0202"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("audit_uid", sa.String(length=32), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_user_uid", sa.String(length=32), nullable=True),
        sa.Column("actor_username", sa.String(length=80), nullable=True),
        sa.Column("actor_role", sa.String(length=20), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_path", sa.String(length=500), nullable=False),
        sa.Column("http_method", sa.String(length=10), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "outcome IN ('success', 'failure')",
            name="ck_audit_events_outcome",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audit_uid"),
    )
    op.create_index(
        op.f("ix_audit_events_occurred_at"),
        "audit_events",
        ["occurred_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_events_actor_user_id"),
        "audit_events",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_events_actor_user_uid"),
        "audit_events",
        ["actor_user_uid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_events_actor_username"),
        "audit_events",
        ["actor_username"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_events_action"),
        "audit_events",
        ["action"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_events_resource_type"),
        "audit_events",
        ["resource_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_events_outcome"),
        "audit_events",
        ["outcome"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_event_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events are append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_event_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS prevent_audit_event_mutation()"
    )

    op.drop_index(
        op.f("ix_audit_events_outcome"),
        table_name="audit_events",
    )
    op.drop_index(
        op.f("ix_audit_events_resource_type"),
        table_name="audit_events",
    )
    op.drop_index(
        op.f("ix_audit_events_action"),
        table_name="audit_events",
    )
    op.drop_index(
        op.f("ix_audit_events_actor_username"),
        table_name="audit_events",
    )
    op.drop_index(
        op.f("ix_audit_events_actor_user_uid"),
        table_name="audit_events",
    )
    op.drop_index(
        op.f("ix_audit_events_actor_user_id"),
        table_name="audit_events",
    )
    op.drop_index(
        op.f("ix_audit_events_occurred_at"),
        table_name="audit_events",
    )
    op.drop_table("audit_events")
