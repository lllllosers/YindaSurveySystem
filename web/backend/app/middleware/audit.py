from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.services.audit_service import AuditActor, record_event_safely


AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if (
            request.method.upper() in AUDITED_METHODS
            and request.url.path.startswith("/api/v1/")
        ):
            actor = AuditActor(
                user_id=getattr(request.state, "audit_user_id", None),
                user_uid=getattr(request.state, "audit_user_uid", None),
                username=getattr(request.state, "audit_username", None),
                role=getattr(request.state, "audit_role", None),
            )
            details = getattr(request.state, "audit_details", None)
            summary = getattr(request.state, "audit_summary", None)

            client_ip = (
                request.client.host
                if request.client is not None
                else None
            )

            record_event_safely(
                actor=actor,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                client_ip=client_ip,
                user_agent=request.headers.get("user-agent"),
                summary=summary,
                details=details,
            )

        return response
