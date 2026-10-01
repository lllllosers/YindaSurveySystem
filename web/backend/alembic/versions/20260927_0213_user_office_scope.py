"""allow reviewer and viewer accounts to be scoped to one office

Revision ID: 20260927_0213
Revises: 20260927_0212
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260927_0213"
down_revision: str | None = "20260927_0212"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("office_scope_uid", sa.String(32)))
    op.create_index("ix_users_office_scope_uid", "users", ["office_scope_uid"])
    op.add_column("registration_invites", sa.Column("office_scope_uid", sa.String(32)))


def downgrade() -> None:
    op.drop_column("registration_invites", "office_scope_uid")
    op.drop_index("ix_users_office_scope_uid", table_name="users")
    op.drop_column("users", "office_scope_uid")
