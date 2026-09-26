from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


def new_online_entry_uid() -> str:
    return uuid4().hex


class OnlineSurveyEntry(Base):
    """Web 端录入的调查草稿及其审核、入库状态。"""

    __tablename__ = "online_survey_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entry_uid: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, default=new_online_entry_uid
    )
    task_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    project_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    survey_batch_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    management_scope_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    organization_unit_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    organization_name: Mapped[str] = mapped_column(String(160), nullable=False)
    canal_unit_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    canal_name: Mapped[str] = mapped_column(String(160), nullable=False)
    form_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    form_name: Mapped[str] = mapped_column(String(240), nullable=False)
    asset_name: Mapped[str | None] = mapped_column(String(300), index=True)
    form_data_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evaluations_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    conclusion_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    media_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="draft", server_default="draft", index=True
    )
    revision_no: Mapped[int] = mapped_column(default=1, nullable=False)
    review_notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_by_username: Mapped[str] = mapped_column(String(80), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_user_uid: Mapped[str | None] = mapped_column(String(32), index=True)
    reviewed_by_username: Mapped[str | None] = mapped_column(String(80))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','submitted','accepted','rejected','imported')",
            name="ck_online_survey_entries_status",
        ),
        CheckConstraint("revision_no >= 1", name="ck_online_survey_entries_revision"),
    )
