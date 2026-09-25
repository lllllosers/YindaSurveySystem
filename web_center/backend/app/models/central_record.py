from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class CentralEngineeringAsset(Base):
    __tablename__ = "central_engineering_assets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    engineering_asset_uid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    project_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    asset_name: Mapped[str | None] = mapped_column(String(300))
    asset_type: Mapped[str | None] = mapped_column(String(100), index=True)
    organization_unit_uid: Mapped[str | None] = mapped_column(String(32), index=True)
    canal_unit_uid: Mapped[str | None] = mapped_column(String(32), index=True)
    business_code: Mapped[str | None] = mapped_column(String(160), index=True)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    current_submission_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CentralSurveyRecord(Base):
    __tablename__ = "central_survey_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    survey_record_uid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    engineering_asset_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    project_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    survey_batch_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    form_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    organization_unit_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    canal_unit_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_task_uid: Mapped[str | None] = mapped_column(String(32), index=True)
    source_management_scope_uid: Mapped[str | None] = mapped_column(String(32), index=True)
    record_status: Mapped[str | None] = mapped_column(String(30), index=True)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    current_submission_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CentralInspectionResult(Base):
    __tablename__ = "central_inspection_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    survey_record_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    item_code: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    current_submission_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("survey_record_uid", "item_code", name="uq_central_inspection_record_item"),
    )


class CentralSurveyMedia(Base):
    __tablename__ = "central_survey_media"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    media_uid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    survey_record_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    package_path: Mapped[str] = mapped_column(String(600), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    current_submission_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
