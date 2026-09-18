from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


def new_stable_uid() -> str:
    return uuid4().hex


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    project_uid: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=new_stable_uid,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        server_default="active",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    batches: Mapped[list["SurveyBatch"]] = relationship(
        back_populates="project",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("project_uid", name="uq_projects_project_uid"),
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_projects_status",
        ),
    )


class SurveyBatch(Base):
    __tablename__ = "survey_batches"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    survey_batch_uid: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=new_stable_uid,
    )
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    batch_name: Mapped[str] = mapped_column(String(200), nullable=False)
    batch_code: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="planned",
        server_default="planned",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[Project] = relationship(back_populates="batches")

    __table_args__ = (
        UniqueConstraint(
            "survey_batch_uid",
            name="uq_survey_batches_uid",
        ),
        UniqueConstraint(
            "project_id",
            "batch_code",
            name="uq_survey_batches_project_code",
        ),
        CheckConstraint(
            "status IN ('planned', 'active', 'closed')",
            name="ck_survey_batches_status",
        ),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_survey_batches_date_range",
        ),
    )
