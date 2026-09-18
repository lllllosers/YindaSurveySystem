from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


def new_audit_uid() -> str:
    return uuid4().hex


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    audit_uid: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False,
        default=new_audit_uid,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
    )
    actor_user_uid: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
    )
    actor_username: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        index=True,
    )
    actor_role: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
    )
    resource_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    http_method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    status_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    client_ip: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    details_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "outcome IN ('success', 'failure')",
            name="ck_audit_events_outcome",
        ),
    )
