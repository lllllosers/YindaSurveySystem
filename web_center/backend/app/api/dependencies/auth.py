from dataclasses import dataclass
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import AuthSession, User
from app.services.auth_service import get_session_by_token, verify_csrf_token
from app.services.security import has_permission


SESSION_COOKIE_NAME = "yd_session"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: AuthSession


def get_auth_context(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> AuthContext:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    session = get_session_by_token(db, token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid.",
        )

    return AuthContext(user=session.user, session=session)


def get_current_user(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> User:
    return context.user


def require_permission(permission: str) -> Callable:
    def dependency(
        request: Request,
        context: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> User:
        if not has_permission(context.user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied.",
            )

        if request.method.upper() not in SAFE_METHODS:
            csrf_token = request.headers.get("X-CSRF-Token")
            if not verify_csrf_token(context.session, csrf_token):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid CSRF token.",
                )

        return context.user

    return dependency
