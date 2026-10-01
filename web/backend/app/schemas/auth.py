from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


UserRole = Literal["admin", "manager", "reviewer", "viewer"]


def normalize_username(value: str) -> str:
    value = value.strip().lower()
    if not value:
        raise ValueError("username cannot be empty")
    if not value.replace("_", "").replace("-", "").isalnum():
        raise ValueError("username supports letters, numbers, underscore and hyphen only")
    return value


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return normalize_username(value)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    invite_code: str | None = Field(default=None, max_length=100)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return normalize_username(value)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("display_name cannot be empty")
        return value


class UserRead(BaseModel):
    user_uid: str
    username: str
    display_name: str
    role: UserRole
    is_active: bool
    is_approved: bool = True
    office_scope_uid: str | None = None
    last_login_at: datetime | None
    created_at: datetime


class AuthMeResponse(UserRead):
    permissions: list[str]


class LoginResponse(BaseModel):
    user: AuthMeResponse
    csrf_token: str


class CsrfResponse(BaseModel):
    csrf_token: str


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=6, max_length=128)
    role: UserRole = "viewer"
    is_active: bool = True
    office_scope_uid: str | None = Field(default=None, min_length=32, max_length=32)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return normalize_username(value)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("display_name cannot be empty")
        return value


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    role: UserRole | None = None
    is_active: bool | None = None
    office_scope_uid: str | None = Field(default=None, min_length=32, max_length=32)


class PendingUserSelection(BaseModel):
    user_uids: list[str] = Field(min_length=1, max_length=200)

    @field_validator("user_uids")
    @classmethod
    def unique_user_uids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("user_uids must be unique")
        if any(len(value) != 32 or not all(char in "0123456789abcdef" for char in value.lower()) for value in values):
            raise ValueError("user_uids must contain valid user identifiers")
        return values


class UserBatchApprove(PendingUserSelection):
    role: Literal["manager", "reviewer", "viewer"] = "viewer"
    office_scope_uid: str | None = Field(default=None, min_length=32, max_length=32)


class UserBatchDismiss(PendingUserSelection):
    pass


class InviteCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    role: Literal["manager", "reviewer", "viewer"] = "viewer"
    max_uses: int = Field(default=20, ge=1, le=200)
    valid_days: int = Field(default=7, ge=1, le=30)
    office_scope_uid: str | None = Field(default=None, min_length=32, max_length=32)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("邀请用途不能为空")
        return value


class InviteRead(BaseModel):
    invite_uid: str
    code_prefix: str
    label: str
    role: Literal["manager", "reviewer", "viewer"]
    office_scope_uid: str | None
    max_uses: int
    used_count: int
    expires_at: datetime
    revoked_at: datetime | None
    created_by_username: str
    created_at: datetime


class InviteCreated(InviteRead):
    code: str


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)
