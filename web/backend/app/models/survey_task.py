from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


def new_task_uid() -> str:
    return uuid4().hex


class SurveyTask(Base):
    __tablename__ = "survey_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_uid: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, default=new_task_uid
    )
    package_uid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    survey_batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("survey_batches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    task_name: Mapped[str] = mapped_column(String(240), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    target_unit_type: Mapped[str] = mapped_column(String(30), nullable=False)
    department_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    department_name: Mapped[str] = mapped_column(String(160), nullable=False)
    organization_unit_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    organization_name: Mapped[str] = mapped_column(String(160), nullable=False)
    parent_task_uid: Mapped[str | None] = mapped_column(String(32), index=True)
    root_task_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    task_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected_scope_uids: Mapped[list] = mapped_column(JSON, nullable=False)
    frozen_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    selected_scope_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_canal_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_organization_count: Mapped[int] = mapped_column(Integer, nullable=False)
    form_count: Mapped[int] = mapped_column(Integer, nullable=False)
    stored_relative_path: Mapped[str] = mapped_column(String(600), unique=True, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="issued", server_default="issued", index=True
    )
    download_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    first_downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_by_username: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "target_unit_type IN ('department','water_office')",
            name="ck_survey_tasks_target_unit_type",
        ),
        CheckConstraint(
            "status IN ('issued','downloaded','result_received','closed','cancelled')",
            name="ck_survey_tasks_status",
        ),
        CheckConstraint("task_depth >= 0", name="ck_survey_tasks_depth"),
        CheckConstraint("selected_scope_count > 0", name="ck_survey_tasks_scope_count"),
        CheckConstraint("file_size >= 0", name="ck_survey_tasks_file_size"),
        CheckConstraint("download_count >= 0", name="ck_survey_tasks_download_count"),
    )
