from datetime import datetime

from pydantic import BaseModel


class AuditEventRead(BaseModel):
    audit_uid: str
    occurred_at: datetime
    actor_user_uid: str | None
    actor_username: str | None
    actor_role: str | None
    action: str
    resource_type: str
    resource_path: str
    http_method: str
    status_code: int
    outcome: str
    client_ip: str | None
    user_agent: str | None
    summary: str | None
    details_json: dict | None


class AuditEventPage(BaseModel):
    items: list[AuditEventRead]
    total: int
    limit: int
    offset: int
