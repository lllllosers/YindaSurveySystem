from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


WEB_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WEB_ROOT))
import portable_runtime as portable  # noqa: E402
from app.core import windows_subprocess  # noqa: E402


@pytest.fixture
def runtime(tmp_path):
    root = tmp_path / "bundle"
    web = root / "web_center"
    (web / "backend").mkdir(parents=True)
    (root / "runtime" / "python").mkdir(parents=True)
    (root / "runtime" / "postgres" / "bin").mkdir(parents=True)
    (root / "runtime" / "python" / "python.exe").touch()
    for name in ("initdb", "pg_ctl", "pg_isready", "psql", "createdb", "pg_dump"):
        (root / "runtime" / "postgres" / "bin" / f"{name}.exe").touch()
    return portable.PortableRuntime(web)


def completed(command, code=0, output="", error=""):
    return subprocess.CompletedProcess(command, code, output, error)


def test_windows_hidden_helper_flags_and_core_commands(monkeypatch):
    options = windows_subprocess.hidden_options()
    assert options["creationflags"] & subprocess.CREATE_NO_WINDOW
    assert options["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW
    assert options["startupinfo"].wShowWindow == subprocess.SW_HIDE
    calls = []
    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return completed(command)
    for executable in ("initdb.exe", "pg_ctl.exe", "pg_isready.exe", "psql.exe", "createdb.exe", "pg_dump.exe", "python.exe"):
        windows_subprocess.hidden_run([executable], runner=runner)
    assert all(kwargs["creationflags"] & subprocess.CREATE_NO_WINDOW for _, kwargs in calls)
    assert all(kwargs["startupinfo"].wShowWindow == subprocess.SW_HIDE for _, kwargs in calls)


def test_pg_ctl_starts_database_and_pg_isready_waits_twice(runtime, monkeypatch):
    runtime.env_file.write_text("DB_HOST=127.0.0.1\nDB_PORT=55432\nDB_PASSWORD=secret\n", encoding="utf-8")
    runtime.data.mkdir(parents=True)
    (runtime.data / "PG_VERSION").write_text("17", encoding="ascii")
    calls = []
    readiness = iter((1, 1, 0))
    def runner(command, **kwargs):
        name = Path(command[0]).name
        calls.append((name, command))
        if name == "pg_ctl.exe" and "status" in command:
            return completed(command, 1)
        if name == "pg_isready.exe":
            return completed(command, next(readiness))
        return completed(command)
    monkeypatch.setattr(portable, "hidden_run", runner)
    monkeypatch.setattr(portable.time, "sleep", lambda seconds: None)
    import socket
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: (_ for _ in ()).throw(OSError()))
    runtime.start_database()
    assert any(name == "pg_ctl.exe" and "start" in command for name, command in calls)
    assert sum(name == "pg_isready.exe" for name, _ in calls) == 3
    assert not any(name == "postgres.exe" for name, _ in calls)


def test_pg_isready_timeout_after_sixty_seconds(runtime, monkeypatch):
    clock = [0.0]
    calls = []
    monkeypatch.setattr(portable.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(portable.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(portable, "hidden_run", lambda command, **kwargs: (calls.append(command), completed(command, 1))[1])
    with pytest.raises(RuntimeError, match="60 秒内未就绪"):
        runtime._wait_until_ready(60.0)
    assert clock[0] == 60.0
    assert len(calls) > 2


def test_pg_ctl_start_failure_is_immediate_and_readable(runtime, monkeypatch):
    runtime.env_file.write_text("DB_HOST=127.0.0.1\nDB_PORT=55432\nDB_PASSWORD=secret\n", encoding="utf-8")
    runtime.data.mkdir(parents=True)
    (runtime.data / "PG_VERSION").write_text("17", encoding="ascii")
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        if "start" in command:
            Path(command[command.index("-l") + 1]).write_bytes(b"pg_ctl: could not start server\n")
        return completed(command, 1, error="pg_ctl: could not start server")
    monkeypatch.setattr(portable, "hidden_run", runner)
    import socket
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: (_ for _ in ()).throw(OSError()))
    with pytest.raises(RuntimeError, match="pg_ctl: could not start server"):
        runtime.start_database()
    assert not any(Path(command[0]).name == "pg_isready.exe" for command in calls)


def test_failed_initialization_can_resume_without_replacing_password_or_data(runtime, monkeypatch):
    calls = []
    first_migration = [True]
    def runner(command, **kwargs):
        name = Path(command[0]).name
        calls.append(command)
        if name == "initdb.exe":
            candidate = Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("--pgdata=")))
            (candidate / "PG_VERSION").write_text("17", encoding="ascii")
        if name == "pg_ctl.exe" and "status" in command:
            return completed(command, 0)
        if name == "psql.exe":
            return completed(command, 0, "1\n")
        if name == "python.exe" and "alembic" in command and first_migration[0]:
            first_migration[0] = False
            return completed(command, 1, error="migration failed")
        return completed(command)
    monkeypatch.setattr(portable, "hidden_run", runner)
    with pytest.raises(RuntimeError, match="migration failed"):
        runtime.initialize("admin", "管理员", "password123")
    password = runtime._password()
    data = runtime.data / "PG_VERSION"
    assert data.is_file()
    runtime.initialize("admin", "管理员", "password123")
    assert runtime._password() == password
    assert data.is_file()
    assert sum(Path(command[0]).name == "initdb.exe" for command in calls) == 1


def test_initialized_database_restarts_without_initdb(runtime, monkeypatch):
    runtime.env_file.write_text("DB_HOST=127.0.0.1\nDB_PORT=55432\nDB_PASSWORD=secret\n", encoding="utf-8")
    runtime.data.mkdir(parents=True)
    (runtime.data / "PG_VERSION").write_text("17", encoding="ascii")
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        if Path(command[0]).name == "psql.exe":
            return completed(command, 0, "1\n")
        return completed(command)
    monkeypatch.setattr(portable, "hidden_run", runner)
    runtime.initialize("admin", "管理员", "password123")
    runtime.initialize("admin", "管理员", "password123")
    assert not any(Path(command[0]).name == "initdb.exe" for command in calls)
