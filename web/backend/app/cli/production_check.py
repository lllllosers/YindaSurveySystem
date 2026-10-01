"""Read-only deployment preflight; never prints secret values."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys
import tempfile

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from pydantic import ValidationError
from sqlalchemy import text


def main() -> int:
    blockers = 0

    def report(level: str, message: str) -> None:
        nonlocal blockers
        print(f"{level}: {message}")
        if level == "BLOCKER":
            blockers += 1

    try:
        from app.core.config import BACKEND_DIR, settings
    except ValidationError as exc:
        for error in exc.errors():
            location = ".".join(map(str, error["loc"])) or "production settings"
            report("BLOCKER", f"Invalid {location}: {error['msg']}")
        print("Preflight: BLOCKER present.")
        return 1

    if settings.app_env == "production":
        report("PASS", "APP_ENV=production; secure cookies and exact hosts validated.")
    else:
        report("BLOCKER", "APP_ENV must be production.")
    if settings.session_cookie_secure:
        report("PASS", "Session cookie requires HTTPS.")
    else:
        report("BLOCKER", "SESSION_COOKIE_SECURE must be true.")
    if settings.db_password and settings.db_password != "replace-with-local-password":
        report("PASS", "Database password is not the example value.")
    else:
        report("BLOCKER", "Database password is still the example value.")
    hosts = settings.trusted_hosts
    if hosts and "*" not in hosts:
        report("PASS", "ALLOWED_HOSTS contains exact hostnames.")
        if all(host in {"127.0.0.1", "localhost", "[::1]"} for host in hosts):
            report("BLOCKER", "ALLOWED_HOSTS does not include a public acceptance host.")
    else:
        report("BLOCKER", "ALLOWED_HOSTS is missing or contains a wildcard.")
    if settings.effective_registration_mode == "open":
        report("WARNING", "Registration is open; invite_only is recommended for public acceptance.")
    else:
        report("PASS", f"Registration mode: {settings.effective_registration_mode}.")

    if settings.app_env == "production":
        from app.main import app

        if app.docs_url is None and app.redoc_url is None and app.openapi_url is None:
            report("PASS", "Production API documentation is disabled.")
        else:
            report("BLOCKER", "Production API documentation is still enabled.")

    frontend = BACKEND_DIR.parent / "frontend" / "dist" / "index.html"
    report("PASS" if frontend.is_file() else "BLOCKER", "Frontend production build exists." if frontend.is_file() else "Missing frontend/dist/index.html.")

    for label in ("storage", "backups"):
        folder = BACKEND_DIR / label
        try:
            folder.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=folder):
                pass
        except OSError:
            report("BLOCKER", f"{label} directory is not writable.")
        else:
            report("PASS", f"{label} directory is writable.")

    try:
        free = shutil.disk_usage(BACKEND_DIR / "storage").free
        if free <= settings.min_free_disk_bytes:
            report("BLOCKER", "Free space on the storage volume is below the reserve.")
        else:
            report("PASS", f"Storage volume has about {free // (1024**3)} GiB free.")
    except OSError:
        report("BLOCKER", "Cannot read storage volume free space.")

    if settings.max_api_request_bytes <= 0 or settings.max_media_upload_bytes <= 0 or settings.max_result_upload_bytes <= 0:
        report("BLOCKER", "Upload limits must be positive.")
    elif settings.max_api_request_bytes > settings.max_media_upload_bytes or settings.max_media_upload_bytes > settings.max_result_upload_bytes:
        report("BLOCKER", "Upload limit ordering is invalid.")
    else:
        report("PASS", "Request body limits are valid.")
    if settings.max_result_upload_bytes > 2 * 1024**3 or settings.max_zip_total_uncompressed_bytes > 8 * 1024**3:
        report("WARNING", "Upload or ZIP expansion limit exceeds the acceptance recommendation.")
    if settings.max_zip_file_count > 10_000 or settings.max_zip_json_bytes > 256 * 1024**2:
        report("WARNING", "ZIP file count or JSON read limit exceeds the acceptance recommendation.")
    if settings.db_host not in {"127.0.0.1", "localhost", "::1"}:
        report("WARNING", "Database host is not loopback; verify its network boundary.")

    try:
        from app.db.session import engine

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            current = MigrationContext.configure(connection).get_current_revision()
        report("PASS", "PostgreSQL connection is healthy.")
        alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
        alembic_config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        head = ScriptDirectory.from_config(alembic_config).get_current_head()
        if current == head:
            report("PASS", "Alembic migration is at head.")
        else:
            report("BLOCKER", "Alembic migration is not at head.")
    except Exception:
        report("BLOCKER", "PostgreSQL connection or Alembic revision check failed.")

    print("Preflight: BLOCKER present." if blockers else "Preflight: no BLOCKER.")
    return 1 if blockers else 0


if __name__ == "__main__":
    sys.exit(main())
