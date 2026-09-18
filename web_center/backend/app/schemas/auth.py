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


class UserRead(BaseModel):
    user_uid: str
    username: str
    display_name: str
    role: UserRole
    is_active: bool
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
    password: str = Field(min_length=10, max_length=128)
    role: UserRole = "viewer"
    is_active: bool = True

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


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=10, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)
