"""Allow desktop UUID media identities without changing existing values.

Revision ID: 20261024_0214
Revises: 20260927_0213
"""

from alembic import op
import sqlalchemy as sa

revision = "20261024_0214"
down_revision = "20260927_0213"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "central_survey_media", "media_uid",
        existing_type=sa.String(32), type_=sa.String(36), existing_nullable=False,
    )


def downgrade() -> None:
    # Hold the lock through the check and ALTER, including concurrent imports.
    # Use SQL so offline migration scripts retain the same safety guarantee.
    op.execute("LOCK TABLE central_survey_media IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM central_survey_media WHERE length(media_uid) > 32) THEN
                RAISE EXCEPTION 'Cannot downgrade: central_survey_media contains media_uid longer than 32 characters';
            END IF;
        END $$
    """)
    op.alter_column(
        "central_survey_media", "media_uid",
        existing_type=sa.String(36), type_=sa.String(32), existing_nullable=False,
    )
