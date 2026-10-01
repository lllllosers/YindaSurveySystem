"""Preflight for a loopback-only, console-controlled portable installation."""

from __future__ import annotations

import sys
import tempfile

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.config import BACKEND_DIR, settings


def main() -> int:
    blockers = 0

    def report(ok: bool, message: str) -> None:
        nonlocal blockers
        print(f"{'PASS' if ok else 'BLOCKER'}: {message}")
        blockers += not ok

    report(settings.app_env == "development", "Portable local mode is development.")
    report(settings.db_host in {"127.0.0.1", "localhost"} and settings.db_port == 55432, "PostgreSQL is bound to the bundled loopback port.")
    report(bool(settings.db_password), "Database password is configured.")
    report((BACKEND_DIR.parent / "frontend" / "dist" / "index.html").is_file(), "Frontend build exists.")
    for name in ("storage", "backups"):
        folder = BACKEND_DIR / name
        try:
            folder.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=folder):
                pass
            report(True, f"{name} is writable.")
        except OSError:
            report(False, f"{name} is not writable.")
    try:
        from app.db.session import engine
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            current = MigrationContext.configure(connection).get_current_revision()
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        head = ScriptDirectory.from_config(config).get_current_head()
        report(current == head, "PostgreSQL is connected and migrations are current.")
    except Exception:
        report(False, "PostgreSQL connection or migration check failed.")
    print("Preflight: no BLOCKER." if not blockers else "Preflight: BLOCKER present.")
    return 1 if blockers else 0


if __name__ == "__main__":
    sys.exit(main())
