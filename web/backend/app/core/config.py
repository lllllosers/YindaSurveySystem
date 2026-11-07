from pathlib import Path
import os
import sys
import re
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


BACKEND_DIR = Path(__file__).resolve().parents[2]
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[4]))


class Settings(BaseSettings):
    app_name: str = "Yinda Survey Web Center API"
    app_env: Literal["development", "test", "production"] = "development"

    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = "yinda_web_center"
    db_user: str = "yinda_app"
    db_password: str = Field(repr=False)

    session_cookie_secure: bool = False
    transport_mode: Literal["https", "lan_http"] = "https"
    data_root: Path | None = None
    allowed_hosts: str = ""
    registration_mode: Literal["open", "invite_only", "closed"] | None = None
    enable_hsts: bool = False

    max_result_upload_bytes: int = Field(default=2 * 1024**3, gt=0)
    max_media_upload_bytes: int = Field(default=1024**3, gt=0)
    max_task_upload_bytes: int = Field(default=512 * 1024**2, gt=0)
    max_desktop_database_upload_bytes: int = Field(default=2 * 1024**3, gt=0)
    max_api_request_bytes: int = Field(default=8 * 1024**2, gt=0)
    max_zip_file_count: int = Field(default=10_000, gt=0)
    max_zip_single_file_bytes: int = Field(default=2 * 1024**3, gt=0)
    max_zip_total_uncompressed_bytes: int = Field(default=8 * 1024**3, gt=0)
    max_zip_json_bytes: int = Field(default=256 * 1024**2, gt=0)
    min_free_disk_bytes: int = Field(default=5 * 1024**3, ge=0)

    model_config = SettingsConfigDict(
        env_file=os.environ.get("YINDA_CONFIG_FILE", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8-sig",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("registration_mode", mode="before")
    @classmethod
    def empty_registration_mode_is_default(cls, value):
        return None if value == "" else value

    @property
    def trusted_hosts(self) -> list[str]:
        return [host.strip().lower() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def effective_registration_mode(self) -> str:
        return self.registration_mode or ("invite_only" if self.app_env == "production" else "open")

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.data_root is not None and not self.data_root.is_absolute():
            raise ValueError("DATA_ROOT must be an absolute persistent directory.")
        if self.app_env != "production":
            return self
        if not self.session_cookie_secure and self.transport_mode != "lan_http":
            raise ValueError("Production requires SESSION_COOKIE_SECURE=true.")
        if self.transport_mode == "lan_http" and (self.session_cookie_secure or self.enable_hsts):
            raise ValueError("LAN HTTP requires SESSION_COOKIE_SECURE=false and ENABLE_HSTS=false.")
        if (len(self.db_password) < 12 or self.db_password.lower() in {
            "replace-with-local-password", "<strong-password>", "password123456", "changeme123456"
        }):
            raise ValueError("Production DB_PASSWORD must be a non-example password of at least 12 characters.")
        hosts = self.trusted_hosts
        if not hosts or any(
            host != "[::1]" and (
                re.fullmatch(r"[a-z0-9][a-z0-9.-]*", host) is None
                or ".." in host or host.endswith(".")
            )
            for host in hosts
        ):
            raise ValueError("Production ALLOWED_HOSTS requires exact hostnames; empty and wildcards are forbidden.")
        if self.max_api_request_bytes > self.max_media_upload_bytes or self.max_media_upload_bytes > self.max_result_upload_bytes:
            raise ValueError("Request limits must satisfy API <= media <= result upload.")
        if self.max_zip_json_bytes > self.max_zip_single_file_bytes:
            raise ValueError("MAX_ZIP_JSON_BYTES cannot exceed MAX_ZIP_SINGLE_FILE_BYTES.")
        return self

    @property
    def file_base(self) -> Path:
        # Retain database values such as storage/tasks/... across relocation.
        return (self.data_root / "data").resolve() if self.data_root else BACKEND_DIR

    @property
    def storage_dir(self) -> Path:
        return self.file_base / "storage"

    @property
    def backups_dir(self) -> Path:
        return self.data_root / "backups" if self.data_root else BACKEND_DIR / "backups"

    @property
    def frontend_dist(self) -> Path:
        return RESOURCE_ROOT / "frontend" if getattr(sys, "frozen", False) else BACKEND_DIR.parent / "frontend" / "dist"

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )


settings = Settings()
