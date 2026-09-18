from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    AuthContext,
    get_auth_context,
    get_current_user,
)
from app.core.config import settings
from app.db.session import get_db
from app.models.auth import User
from app.schemas.auth import (
    AuthMeResponse,
    ChangePasswordRequest,
    CsrfResponse,
    LoginRequest,
    LoginResponse,
)
from app.services import auth_service
from app.services.security import (
    permissions_for_role,
    verify_password,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

DbSession = Annotated[
    Session,
    Depends(get_db),
]
CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]
CurrentContext = Annotated[
    AuthContext,
    Depends(get_auth_context),
]


def user_payload(
    user: User,
) -> AuthMeResponse:
    return AuthMeResponse(
        user_uid=user.user_uid,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        permissions=sorted(
            permissions_for_role(user.role)
        ),
    )


def set_session_cookie(
    response: Response,
    token: str,
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=auth_service.SESSION_HOURS * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def set_csrf_cookie(
    response: Response,
    csrf_token: str,
) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=auth_service.SESSION_HOURS * 3600,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(
    response: Response,
) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
    )
    response.delete_cookie(
        CSRF_COOKIE_NAME,
        path="/",
    )


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
):
    try:
        user = auth_service.authenticate_user(
            db,
            payload.username,
            payload.password,
        )
    except auth_service.AccountLockedError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
        ) from exc
    except auth_service.InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    request.state.audit_user_id = user.id
    request.state.audit_user_uid = user.user_uid
    request.state.audit_username = user.username
    request.state.audit_role = user.role
    request.state.audit_summary = "用户登录成功"

    _, token, csrf_token = (
        auth_service.create_session(
            db,
            user,
        )
    )

    set_session_cookie(
        response,
        token,
    )
    set_csrf_cookie(
        response,
        csrf_token,
    )

    return LoginResponse(
        user=user_payload(user),
        csrf_token=csrf_token,
    )


@router.get(
    "/me",
    response_model=AuthMeResponse,
)
def me(
    user: CurrentUser,
):
    return user_payload(user)


@router.get(
    "/csrf",
    response_model=CsrfResponse,
)
def csrf(
    response: Response,
    context: CurrentContext,
    db: DbSession,
):
    csrf_token = (
        auth_service.rotate_csrf_token(
            db,
            context.session,
        )
    )

    set_csrf_cookie(
        response,
        csrf_token,
    )

    return CsrfResponse(
        csrf_token=csrf_token,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    request: Request,
    context: CurrentContext,
    db: DbSession,
):
    csrf_token = request.headers.get(
        "X-CSRF-Token"
    )

    if not auth_service.verify_csrf_token(
        context.session,
        csrf_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token.",
        )

    auth_service.revoke_session(
        db,
        context.session,
    )

    response = Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
    clear_auth_cookies(response)
    return response


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    context: CurrentContext,
    db: DbSession,
):
    csrf_token = request.headers.get(
        "X-CSRF-Token"
    )

    if not auth_service.verify_csrf_token(
        context.session,
        csrf_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token.",
        )

    if not verify_password(
        payload.current_password,
        context.user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    if (
        payload.current_password
        == payload.new_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "New password must differ "
                "from current password."
            ),
        )

    auth_service.reset_password(
        db,
        context.user,
        payload.new_password,
    )

    response = Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
    clear_auth_cookies(response)
    return response
