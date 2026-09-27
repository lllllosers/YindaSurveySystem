from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.auth import AuthSession, RegistrationInvite, User
from app.models.master_data import MasterOffice
from app.models.online_entry import OnlineSurveyEntry
from app.models.result_submission import ResultSubmission
from app.models.survey_task import SurveyTask
from app.schemas.auth import InviteCreate, PendingUserSelection, RegisterRequest, UserBatchApprove, UserCreate, UserUpdate
from app.services.security import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    new_csrf_token,
    new_session_token,
    token_digest,
    verify_password,
)

MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15
SESSION_HOURS = 12


class DuplicateUsernameError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


class AccountLockedError(ValueError):
    pass


class LastAdminError(ValueError):
    pass


class SelfProtectionError(ValueError):
    pass


class PendingApprovalError(ValueError):
    pass


class InvalidInviteError(ValueError):
    pass


class UserInUseError(ValueError):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username.strip().lower()))


def get_user_by_uid(db: Session, user_uid: str) -> User | None:
    return db.scalar(select(User).where(User.user_uid == user_uid))


def list_users(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User).order_by(
                User.is_approved.asc(),
                User.created_at.desc(),
                User.id.desc(),
            )
        )
    )


def validated_office_scope(db: Session, role: str, office_uid: str | None) -> str | None:
    if role in {"admin", "manager"}:
        return None
    if office_uid and db.scalar(select(MasterOffice.id).where(MasterOffice.stable_uid == office_uid)) is None:
        raise ValueError("指定的管理所不存在。")
    return office_uid


def create_user(db: Session, payload: UserCreate) -> User:
    if get_user_by_username(db, payload.username) is not None:
        raise DuplicateUsernameError("Username already exists.")

    user = User(
        username=payload.username,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
        office_scope_uid=validated_office_scope(db, payload.role, payload.office_scope_uid),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def register_user(db: Session, payload: RegisterRequest) -> User:
    if get_user_by_username(db, payload.username) is not None:
        raise DuplicateUsernameError("Username already exists.")

    invite = None
    code = (payload.invite_code or "").strip()
    if code:
        invite = db.scalar(
            select(RegistrationInvite)
            .where(RegistrationInvite.code_hash == sha256(code.encode("utf-8")).hexdigest())
            .with_for_update()
        )
        if invite is None or invite.revoked_at is not None or invite.expires_at <= utcnow() or invite.used_count >= invite.max_uses:
            db.rollback()
            raise InvalidInviteError("邀请口令无效、已到期或已用完，请联系管理员。")

    user = User(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role=invite.role if invite else "viewer",
        is_active=invite is not None,
        is_approved=invite is not None,
        office_scope_uid=invite.office_scope_uid if invite else None,
    )
    db.add(user)
    if invite is not None:
        invite.used_count += 1
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateUsernameError("Username already exists.") from exc
    db.refresh(user)
    return user


def create_invite(db: Session, payload: InviteCreate, actor: User) -> tuple[RegistrationInvite, str]:
    code = "YD-" + secrets.token_urlsafe(24)
    row = RegistrationInvite(
        code_hash=sha256(code.encode("utf-8")).hexdigest(),
        code_prefix=code[:12],
        label=payload.label,
        role=payload.role,
        office_scope_uid=validated_office_scope(db, payload.role, payload.office_scope_uid),
        max_uses=payload.max_uses,
        expires_at=utcnow() + timedelta(days=payload.valid_days),
        created_by_username=actor.username,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, code


def list_invites(db: Session) -> list[RegistrationInvite]:
    return list(db.scalars(select(RegistrationInvite).order_by(RegistrationInvite.id.desc()).limit(200)))


def revoke_invite(db: Session, invite_uid: str) -> RegistrationInvite | None:
    row = db.scalar(
        select(RegistrationInvite)
        .where(RegistrationInvite.invite_uid == invite_uid)
        .with_for_update()
    )
    if row is None:
        return None
    if row.revoked_at is None:
        row.revoked_at = utcnow()
        db.commit()
        db.refresh(row)
    return row


def active_admin_count(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count(User.id)).where(
                User.role == "admin",
                User.is_active.is_(True),
            )
        )
        or 0
    )


def update_user(
    db: Session,
    user: User,
    payload: UserUpdate,
    actor: User,
) -> User:
    values = payload.model_dump(exclude_unset=True)

    if "display_name" in values and values["display_name"] is not None:
        values["display_name"] = values["display_name"].strip()

    next_role = values.get("role") or user.role
    next_office = values.get("office_scope_uid", user.office_scope_uid)
    values["office_scope_uid"] = validated_office_scope(db, next_role, next_office)

    if user.id == actor.id:
        if values.get("is_active") is False:
            raise SelfProtectionError("You cannot disable your own account.")
        if "role" in values and values["role"] != user.role:
            raise SelfProtectionError("You cannot change your own role.")

    removes_active_admin = (
        user.role == "admin"
        and user.is_active
        and (
            values.get("is_active") is False
            or ("role" in values and values["role"] != "admin")
        )
    )
    if removes_active_admin and active_admin_count(db) <= 1:
        raise LastAdminError("At least one active administrator is required.")

    for key, value in values.items():
        setattr(user, key, value)

    if values.get("is_active") is True:
        user.is_approved = True

    if values.get("is_active") is False:
        revoke_all_sessions(db, user.id, commit=False)

    db.commit()
    db.refresh(user)
    return user


def _pending_users(db: Session, payload: PendingUserSelection) -> list[User]:
    rows = list(
        db.scalars(
            select(User)
            .where(User.user_uid.in_(payload.user_uids))
            .with_for_update()
        )
    )
    by_uid = {user.user_uid: user for user in rows}
    if len(by_uid) != len(payload.user_uids):
        db.rollback()
        raise PendingApprovalError("部分申请账户不存在，请刷新列表后重试。")
    if any(user.is_approved or user.is_active for user in rows):
        db.rollback()
        raise PendingApprovalError("所选账户中有已经处理的申请，请刷新列表后重试。")

    return [by_uid[uid] for uid in payload.user_uids]


def approve_pending_users(db: Session, payload: UserBatchApprove) -> list[User]:
    rows = _pending_users(db, payload)
    office_scope_uid = validated_office_scope(db, payload.role, payload.office_scope_uid)
    for user in rows:
        user.role = payload.role
        user.is_approved = True
        user.is_active = True
        user.office_scope_uid = office_scope_uid
        user.failed_login_count = 0
        user.locked_until = None
    db.commit()
    return rows


def dismiss_pending_users(db: Session, payload: PendingUserSelection) -> list[str]:
    rows = _pending_users(db, payload)
    usernames = [user.username for user in rows]
    for user in rows:
        db.delete(user)
    db.commit()
    return usernames


def delete_unused_user(db: Session, user: User, actor: User) -> None:
    if user.id == actor.id:
        raise SelfProtectionError("不能删除当前登录账户。")
    if user.role == "admin" and user.is_active and active_admin_count(db) <= 1:
        raise LastAdminError("至少保留一名启用的管理员。")
    references = (
        (SurveyTask, SurveyTask.created_by_user_uid),
        (OnlineSurveyEntry, OnlineSurveyEntry.created_by_user_uid),
        (OnlineSurveyEntry, OnlineSurveyEntry.reviewed_by_user_uid),
        (ResultSubmission, ResultSubmission.uploader_user_uid),
        (ResultSubmission, ResultSubmission.reviewed_by_user_uid),
    )
    if any(db.scalar(select(model.id).where(column == user.user_uid).limit(1)) is not None for model, column in references):
        raise UserInUseError("账户已参与任务、录入或成果审核，请禁用并撤销会话，以保留历史责任记录。")
    db.delete(user)
    db.commit()


def reset_password(db: Session, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    user.password_changed_at = utcnow()
    user.failed_login_count = 0
    user.locked_until = None
    revoke_all_sessions(db, user.id, commit=False)
    db.commit()


def authenticate_user(db: Session, username: str, password: str) -> User:
    user = get_user_by_username(db, username)
    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        raise InvalidCredentialsError("Invalid username or password.")

    now = utcnow()
    if user.locked_until is not None and user.locked_until > now:
        raise AccountLockedError("Too many failed attempts. Try again later.")

    if not user.is_active or not verify_password(password, user.password_hash):
        if user.is_active:
            user.failed_login_count += 1
            if user.failed_login_count >= MAX_FAILED_LOGINS:
                user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            db.commit()
        raise InvalidCredentialsError("Invalid username or password.")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()
    db.refresh(user)
    return user


def create_session(db: Session, user: User) -> tuple[AuthSession, str, str]:
    token = new_session_token()
    csrf = new_csrf_token()
    now = utcnow()

    session = AuthSession(
        user_id=user.id,
        token_hash=token_digest(token),
        csrf_token_hash=token_digest(csrf),
        expires_at=now + timedelta(hours=SESSION_HOURS),
        last_seen_at=now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, token, csrf


def get_session_by_token(db: Session, token: str) -> AuthSession | None:
    session = db.scalar(
        select(AuthSession)
        .options(joinedload(AuthSession.user))
        .where(AuthSession.token_hash == token_digest(token))
    )
    if session is None:
        return None

    now = utcnow()
    if (
        session.revoked_at is not None
        or session.expires_at <= now
        or not session.user.is_active
    ):
        return None

    if session.last_seen_at < now - timedelta(minutes=5):
        session.last_seen_at = now
        db.commit()

    return session


def rotate_csrf_token(db: Session, session: AuthSession) -> str:
    csrf = new_csrf_token()
    session.csrf_token_hash = token_digest(csrf)
    db.commit()
    return csrf


def verify_csrf_token(session: AuthSession, csrf_token: str | None) -> bool:
    import hmac

    if not csrf_token:
        return False
    return hmac.compare_digest(
        session.csrf_token_hash,
        token_digest(csrf_token),
    )


def revoke_session(db: Session, session: AuthSession) -> None:
    if session.revoked_at is None:
        session.revoked_at = utcnow()
        db.commit()


def revoke_all_sessions(
    db: Session,
    user_id: int,
    *,
    commit: bool = True,
) -> None:
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=utcnow())
    )
    if commit:
        db.commit()
