"""add bounded registration invitations

Revision ID: 20260927_0212
Revises: 20260927_0211
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260927_0212"
down_revision: str | None = "20260927_0211"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "registration_invites",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("invite_uid", sa.String(32), nullable=False, unique=True),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("code_prefix", sa.String(12), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("used_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_username", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('manager','reviewer','viewer')", name="ck_registration_invites_role"),
        sa.CheckConstraint("max_uses >= 1 AND max_uses <= 200", name="ck_registration_invites_max_uses"),
        sa.CheckConstraint("used_count >= 0 AND used_count <= max_uses", name="ck_registration_invites_used_count"),
    )
    op.create_index("ix_registration_invites_expires_at", "registration_invites", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_registration_invites_expires_at", table_name="registration_invites")
    op.drop_table("registration_invites")
