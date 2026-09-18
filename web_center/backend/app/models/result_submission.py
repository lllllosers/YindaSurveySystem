from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


def new_submission_uid() -> str:
    return uuid4().hex


class ResultSubmission(Base):
    __tablename__ = "result_submissions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    submission_uid: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, default=new_submission_uid
    )
    package_uid: Mapped[str | None] = mapped_column(String(32), unique=True)
    result_uid: Mapped[str | None] = mapped_column(String(32), unique=True)
    project_uid: Mapped[str | None] = mapped_column(String(32), index=True)
    survey_batch_uid: Mapped[str | None] = mapped_column(String(32), index=True)

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_relative_path: Mapped[str] = mapped_column(String(600), unique=True, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    package_format_version: Mapped[str | None] = mapped_column(String(30))
    desktop_app_version: Mapped[str | None] = mapped_column(String(50))
    desktop_app_version_label: Mapped[str | None] = mapped_column(String(100))
    result_name: Mapped[str | None] = mapped_column(String(255))
    source_task_uids: Mapped[list | None] = mapped_column(JSON)
    counts_json: Mapped[dict | None] = mapped_column(JSON)

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="uploaded", server_default="uploaded", index=True
    )
    inspection_error_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    inspection_issues_json: Mapped[list | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)

    uploader_user_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    uploader_username: Mapped[str] = mapped_column(String(80), nullable=False)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("file_size >= 0", name="ck_result_submissions_file_size"),
        CheckConstraint(
            "inspection_error_count >= 0",
            name="ck_result_submissions_error_count",
        ),
        CheckConstraint(
            "status IN ("
            "'uploaded','inspected','invalid','preflight_passed',"
            "'conflict','reviewing','accepted','rejected'"
            ")",
            name="ck_result_submissions_status",
        ),
    )
