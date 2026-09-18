from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_permission
from app.db.session import get_db
from app.models.auth import User
from app.schemas.auth import (
    PasswordResetRequest,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.services import auth_service


router = APIRouter(prefix="/users", tags=["Users"])
DbSession = Annotated[Session, Depends(get_db)]
AdminUser = Annotated[
    User,
    Depends(require_permission("users.manage")),
]


def to_user_read(user: User) -> UserRead:
    return UserRead(
        user_uid=user.user_uid,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


def require_user(db: Session, user_uid: str) -> User:
    user = auth_service.get_user_by_uid(db, user_uid)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


@router.get("", response_model=list[UserRead])
def get_users(_: AdminUser, db: DbSession):
    return [to_user_read(user) for user in auth_service.list_users(db)]


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def post_user(payload: UserCreate, _: AdminUser, db: DbSession):
    try:
        user = auth_service.create_user(db, payload)
    except auth_service.DuplicateUsernameError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return to_user_read(user)


@router.patch("/{user_uid}", response_model=UserRead)
def patch_user(
    user_uid: str,
    payload: UserUpdate,
    actor: AdminUser,
    db: DbSession,
):
    user = require_user(db, user_uid)
    try:
        updated = auth_service.update_user(
            db,
            user,
            payload,
            actor,
        )
    except (
        auth_service.LastAdminError,
        auth_service.SelfProtectionError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return to_user_read(updated)


@router.post(
    "/{user_uid}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
)
def reset_password(
    user_uid: str,
    payload: PasswordResetRequest,
    _: AdminUser,
    db: DbSession,
):
    user = require_user(db, user_uid)
    auth_service.reset_password(db, user, payload.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{user_uid}/revoke-sessions",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_sessions(
    user_uid: str,
    _: AdminUser,
    db: DbSession,
):
    user = require_user(db, user_uid)
    auth_service.revoke_all_sessions(db, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
