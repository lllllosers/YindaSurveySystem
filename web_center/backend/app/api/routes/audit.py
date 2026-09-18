from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_permission
from app.db.session import get_db
from app.models.auth import User
from app.schemas.audit import AuditEventPage, AuditEventRead
from app.services.audit_service import list_events


router = APIRouter(prefix="/audit-events", tags=["Audit"])
DbSession = Annotated[Session, Depends(get_db)]
AuditReader = Annotated[
    User,
    Depends(require_permission("audit.read")),
]


@router.get("", response_model=AuditEventPage)
def get_audit_events(
    _: AuditReader,
    db: DbSession,
    actor_username: str | None = Query(default=None, max_length=80),
    resource_type: str | None = Query(default=None, max_length=80),
    action: str | None = Query(default=None, max_length=80),
    outcome: str | None = Query(default=None, pattern="^(success|failure)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    items, total = list_events(
        db,
        actor_username=actor_username,
        resource_type=resource_type,
        action=action,
        outcome=outcome,
        limit=limit,
        offset=offset,
    )
    return AuditEventPage(
        items=[
            AuditEventRead(
                audit_uid=item.audit_uid,
                occurred_at=item.occurred_at,
                actor_user_uid=item.actor_user_uid,
                actor_username=item.actor_username,
                actor_role=item.actor_role,
                action=item.action,
                resource_type=item.resource_type,
                resource_path=item.resource_path,
                http_method=item.http_method,
                status_code=item.status_code,
                outcome=item.outcome,
                client_ip=item.client_ip,
                user_agent=item.user_agent,
                summary=item.summary,
                details_json=item.details_json,
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
