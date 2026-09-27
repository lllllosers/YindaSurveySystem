from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_permission
from app.db.session import get_db
from app.models.auth import User
from app.schemas.auth import (
    InviteCreate,
    InviteCreated,
    InviteRead,
    PasswordResetRequest,
    UserBatchApprove,
    UserBatchDismiss,
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
        is_approved=user.is_approved,
        office_scope_uid=user.office_scope_uid,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


def to_invite_read(row) -> InviteRead:
    return InviteRead(
        invite_uid=row.invite_uid,
        code_prefix=row.code_prefix,
        label=row.label,
        role=row.role,
        office_scope_uid=row.office_scope_uid,
        max_uses=row.max_uses,
        used_count=row.used_count,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        created_by_username=row.created_by_username,
        created_at=row.created_at,
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
    except (auth_service.DuplicateUsernameError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return to_user_read(user)


@router.post("/batch-approve", response_model=list[UserRead])
def batch_approve_users(
    payload: UserBatchApprove,
    request: Request,
    _: AdminUser,
    db: DbSession,
):
    try:
        users = auth_service.approve_pending_users(db, payload)
    except (auth_service.PendingApprovalError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    request.state.audit_summary = "批量审核并启用注册账户"
    request.state.audit_details = {"count": len(users), "role": payload.role, "office_scope_uid": payload.office_scope_uid}
    return [to_user_read(user) for user in users]


@router.post("/batch-dismiss")
def batch_dismiss_users(
    payload: UserBatchDismiss,
    request: Request,
    _: AdminUser,
    db: DbSession,
):
    try:
        usernames = auth_service.dismiss_pending_users(db, payload)
    except auth_service.PendingApprovalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    request.state.audit_summary = "批量清理未通过的注册申请"
    request.state.audit_details = {"count": len(usernames), "usernames": usernames}
    return {"dismissed": len(usernames)}


@router.get("/invites", response_model=list[InviteRead])
def get_invites(_: AdminUser, db: DbSession):
    return [to_invite_read(row) for row in auth_service.list_invites(db)]


@router.post("/invites", response_model=InviteCreated, status_code=status.HTTP_201_CREATED)
def post_invite(payload: InviteCreate, request: Request, actor: AdminUser, db: DbSession):
    try:
        row, code = auth_service.create_invite(db, payload, actor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    request.state.audit_summary = "创建注册邀请口令"
    request.state.audit_details = {"invite_uid": row.invite_uid, "role": row.role, "max_uses": row.max_uses}
    return InviteCreated(**to_invite_read(row).model_dump(), code=code)


@router.post("/invites/{invite_uid}/revoke", response_model=InviteRead)
def post_revoke_invite(invite_uid: str, request: Request, _: AdminUser, db: DbSession):
    row = auth_service.revoke_invite(db, invite_uid)
    if row is None:
        raise HTTPException(status_code=404, detail="邀请口令不存在。")
    request.state.audit_summary = "停用注册邀请口令"
    request.state.audit_details = {"invite_uid": row.invite_uid}
    return to_invite_read(row)


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
        ValueError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return to_user_read(updated)


@router.delete("/{user_uid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_uid: str, request: Request, actor: AdminUser, db: DbSession):
    user = require_user(db, user_uid)
    try:
        auth_service.delete_unused_user(db, user, actor)
    except (auth_service.SelfProtectionError, auth_service.LastAdminError, auth_service.UserInUseError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    request.state.audit_summary = "删除未参与业务的账户"
    request.state.audit_details = {"user_uid": user_uid, "username": user.username}
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
