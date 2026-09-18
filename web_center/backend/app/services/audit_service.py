from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.audit import AuditEvent


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuditActor:
    user_id: int | None = None
    user_uid: str | None = None
    username: str | None = None
    role: str | None = None


def classify_resource(path: str) -> str:
    normalized = path.strip("/")
    parts = normalized.split("/")
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
        return parts[2]
    return "system"


def classify_action(method: str, path: str) -> str:
    method = method.upper()
    resource = classify_resource(path)

    if resource == "auth":
        if path.endswith("/login"):
            return "auth.login"
        if path.endswith("/logout"):
            return "auth.logout"
        if path.endswith("/change-password"):
            return "auth.change_password"

    verbs = {
        "POST": "create",
        "PUT": "replace",
        "PATCH": "update",
        "DELETE": "delete",
    }
    return f"{resource}.{verbs.get(method, method.lower())}"


def record_event_safely(
    *,
    actor: AuditActor,
    method: str,
    path: str,
    status_code: int,
    client_ip: str | None,
    user_agent: str | None,
    summary: str | None = None,
    details: dict | None = None,
) -> None:
    try:
        with SessionLocal() as db:
            event = AuditEvent(
                actor_user_id=actor.user_id,
                actor_user_uid=actor.user_uid,
                actor_username=actor.username,
                actor_role=actor.role,
                action=classify_action(method, path),
                resource_type=classify_resource(path),
                resource_path=path[:500],
                http_method=method.upper()[:10],
                status_code=status_code,
                outcome="success" if status_code < 400 else "failure",
                client_ip=(client_ip or None),
                user_agent=(user_agent[:500] if user_agent else None),
                summary=summary,
                details_json=details,
            )
            db.add(event)
            db.commit()
    except Exception:
        logger.exception("Failed to persist audit event.")


def list_events(
    db: Session,
    *,
    actor_username: str | None,
    resource_type: str | None,
    action: str | None,
    outcome: str | None,
    limit: int,
    offset: int,
) -> tuple[list[AuditEvent], int]:
    filters = []

    if actor_username:
        filters.append(AuditEvent.actor_username.ilike(f"%{actor_username.strip()}%"))
    if resource_type:
        filters.append(AuditEvent.resource_type == resource_type.strip())
    if action:
        filters.append(AuditEvent.action == action.strip())
    if outcome:
        filters.append(AuditEvent.outcome == outcome.strip())

    total = int(
        db.scalar(
            select(func.count(AuditEvent.id)).where(*filters)
        )
        or 0
    )

    items = list(
        db.scalars(
            select(AuditEvent)
            .where(*filters)
            .order_by(
                AuditEvent.occurred_at.desc(),
                AuditEvent.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total
