import hashlib
import secrets

from pwdlib import PasswordHash


_password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = _password_hash.hash("dummy-password-used-only-for-timing")

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {"*"},
    "manager": {
        "projects.read", "projects.write",
        "batches.read", "batches.write",
        "master_data.read",
        "tasks.read", "tasks.write",
        "results.read", "results.upload",
        "audit.read",
        "results.verify",
    },
    "reviewer": {
        "projects.read", "batches.read", "master_data.read",
        "tasks.read", "results.read", "results.review",
    },
    "viewer": {
        "projects.read", "batches.read", "master_data.read",
        "tasks.read", "results.read",
    },
}


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return _password_hash.verify(password, encoded)


def new_session_token() -> str:
    return secrets.token_urlsafe(48)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def permissions_for_role(role: str) -> set[str]:
    return set(ROLE_PERMISSIONS.get(role, set()))


def has_permission(role: str, permission: str) -> bool:
    permissions = permissions_for_role(role)
    return "*" in permissions or permission in permissions
