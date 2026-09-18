from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload

from app.models.auth import AuthSession, User
from app.schemas.auth import UserCreate, UserUpdate
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


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username.strip().lower()))


def get_user_by_uid(db: Session, user_uid: str) -> User | None:
    return db.scalar(select(User).where(User.user_uid == user_uid))


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at, User.id)))


def create_user(db: Session, payload: UserCreate) -> User:
    if get_user_by_username(db, payload.username) is not None:
        raise DuplicateUsernameError("Username already exists.")

    user = User(
        username=payload.username,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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

    if values.get("is_active") is False:
        revoke_all_sessions(db, user.id, commit=False)

    db.commit()
    db.refresh(user)
    return user


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
