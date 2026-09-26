from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


def new_master_uid() -> str:
    return uuid4().hex


class MasterDataState(Base):
    __tablename__ = "master_data_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    base_version: Mapped[str] = mapped_column(String(120), nullable=False)
    source_description: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by_username: Mapped[str | None] = mapped_column(String(80))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (CheckConstraint("revision_no >= 1", name="ck_master_data_state_revision"),)


class MasterDepartment(Base):
    __tablename__ = "master_departments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stable_uid: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, default=new_master_uid)
    master_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    business_code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (CheckConstraint("status IN ('active','inactive')", name="ck_master_departments_status"),)


class MasterOffice(Base):
    __tablename__ = "master_offices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stable_uid: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, default=new_master_uid)
    master_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    parent_department_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    business_code: Mapped[str] = mapped_column(String(40), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("parent_department_uid", "business_code", name="uq_master_office_parent_code"),
        CheckConstraint("status IN ('active','inactive')", name="ck_master_offices_status"),
    )


class MasterCanal(Base):
    __tablename__ = "master_canals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stable_uid: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, default=new_master_uid)
    master_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    parent_canal_uid: Mapped[str | None] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    canal_level: Mapped[str] = mapped_column(String(10), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (CheckConstraint("status IN ('active','inactive')", name="ck_master_canals_status"),)


class MasterManagementScope(Base):
    __tablename__ = "master_management_scopes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stable_uid: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, default=new_master_uid)
    master_key: Mapped[str] = mapped_column(String(140), nullable=False, unique=True)
    canal_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    organization_unit_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    range_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    start_stake_text: Mapped[str | None] = mapped_column(String(40))
    start_stake_value: Mapped[float | None] = mapped_column(Float)
    end_stake_text: Mapped[str | None] = mapped_column(String(40))
    end_stake_value: Mapped[float | None] = mapped_column(Float)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('active','inactive')", name="ck_master_management_scopes_status"),
        CheckConstraint(
            "range_mode IN ('whole','segment_known','segment_unknown')",
            name="ck_master_management_scopes_range_mode",
        ),
        CheckConstraint(
            "(range_mode = 'segment_known' AND start_stake_value IS NOT NULL AND end_stake_value IS NOT NULL AND start_stake_value <= end_stake_value) OR "
            "(range_mode IN ('whole','segment_unknown') AND start_stake_text IS NULL AND start_stake_value IS NULL AND end_stake_text IS NULL AND end_stake_value IS NULL)",
            name="ck_master_management_scopes_range_values",
        ),
    )
