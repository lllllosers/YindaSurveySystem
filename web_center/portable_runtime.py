"""Local PostgreSQL lifecycle for the console-controlled Windows portable bundle."""

from __future__ import annotations

import locale
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time

from backend.app.core.windows_subprocess import hidden_run

DB_PORT = 55432
READY_TIMEOUT_SECONDS = 60


class PortableRuntime:
    def __init__(self, web_root: Path):
        self.web_root = web_root.resolve()
        self.root = self.web_root.parent
        self.pg_bin = self.root / "runtime" / "postgres" / "bin"
        self.data = self.root / "data" / "postgres"
        self.backend = self.web_root / "backend"
        self.env_file = self.backend / ".env"
        self.python = self.root / "runtime" / "python" / "python.exe"

    @property
    def available(self) -> bool:
        return self.python.is_file() and (self.pg_bin / "initdb.exe").is_file()

    def _password(self) -> str:
        if not self.env_file.is_file():
            raise RuntimeError("便携环境尚未初始化，请先点击“初始化便携环境”。")
        for line in self.env_file.read_text(encoding="utf-8-sig").splitlines():
            if line.startswith("DB_PASSWORD="):
                return line.partition("=")[2].strip()
        raise RuntimeError(".env 缺少数据库密码，请检查配置。")

    def _check_database_address(self) -> None:
        values = {}
        for line in self.env_file.read_text(encoding="utf-8-sig").splitlines():
            name, separator, value = line.partition("=")
            if separator:
                values[name.strip()] = value.strip()
        if values.get("DB_HOST") not in {"127.0.0.1", "localhost"} or values.get("DB_PORT") != str(DB_PORT):
            raise RuntimeError("便携包数据库必须使用本机 127.0.0.1:55432，请检查 .env。")

    def _environment(self, *, password: str | None = None) -> dict[str, str]:
        env = os.environ.copy()
        env["PATH"] = str(self.pg_bin) + os.pathsep + env.get("PATH", "")
        env["LC_MESSAGES"] = "C"
        env["LANG"] = "C"
        env["PGCLIENTENCODING"] = "UTF8"
        env["PYTHONIOENCODING"] = "utf-8"
        if password is not None:
            env["PGPASSWORD"] = password
        return env

    def _run(self, command: list[str], *, password: str | None = None, cwd: Path | None = None, input_text: str | None = None, timeout: int = 120) -> str:
        is_python = Path(command[0]).name.lower() in {"python.exe", "pythonw.exe"}
        encoding = "utf-8" if is_python else ("mbcs" if os.name == "nt" else locale.getpreferredencoding(False))
        result = hidden_run(
            command, cwd=cwd, env=self._environment(password=password),
            input=input_text, capture_output=True, text=True,
            encoding=encoding, errors="replace", timeout=timeout,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()[-500:]
            raise RuntimeError(f"便携环境操作失败（退出码 {result.returncode}）：{detail}")
        return result.stdout.strip()

    def initialize(self, username: str, display_name: str, admin_password: str) -> str:
        if not self.available:
            raise RuntimeError("便携包缺少 Python 或 PostgreSQL 运行时。")
        if not username.strip() or not 6 <= len(admin_password) <= 128:
            raise RuntimeError("请填写管理员账号和 6～128 位密码。")
        if self.data.exists() and not self.env_file.is_file():
            raise RuntimeError("已有数据库目录但缺少 .env；请先恢复原配置，避免覆盖现有数据。")
        if not self.env_file.exists():
            db_password = secrets.token_hex(32)
            self.env_file.write_text(
                "APP_NAME=Yinda Survey Web Center API\n"
                "APP_ENV=development\n"
                "DB_HOST=127.0.0.1\n"
                f"DB_PORT={DB_PORT}\n"
                "DB_NAME=yinda_web_center\n"
                "DB_USER=yinda_app\n"
                f"DB_PASSWORD={db_password}\n"
                "SESSION_COOKIE_SECURE=false\n"
                "ALLOWED_HOSTS=127.0.0.1,localhost\n"
                "REGISTRATION_MODE=invite_only\n"
                "PUBLIC_BASE_URL=\n",
                encoding="utf-8",
            )
        db_password = self._password()
        if not (self.data / "PG_VERSION").is_file():
            if self.data.exists():
                raise RuntimeError("数据库目录不完整，请检查 data/postgres。")
            self.data.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="postgres-init-", dir=self.data.parent) as temporary:
                candidate = Path(temporary)
                password_file = candidate.parent / f"pg-password-{os.getpid()}.tmp"
                try:
                    password_file.write_text(db_password, encoding="ascii")
                    self._run([
                        str(self.pg_bin / "initdb.exe"), f"--pgdata={candidate}",
                        "--username=yinda_app", "--auth=scram-sha-256",
                        f"--pwfile={password_file}", "--encoding=UTF8", "--locale=C",
                    ], timeout=180)
                finally:
                    password_file.unlink(missing_ok=True)
                candidate.rename(self.data)
        self.start_database()
        exists = self._run([
            str(self.pg_bin / "psql.exe"), "-X", "-t", "-A", "-h", "127.0.0.1",
            "-p", str(DB_PORT), "-U", "yinda_app", "-d", "postgres", "-c",
            "SELECT 1 FROM pg_database WHERE datname = 'yinda_web_center'",
        ], password=db_password)
        if exists != "1":
            self._run([str(self.pg_bin / "createdb.exe"), "-h", "127.0.0.1", "-p", str(DB_PORT), "-U", "yinda_app", "yinda_web_center"], password=db_password)
        self._run([str(self.python), "-m", "alembic", "upgrade", "head"], cwd=self.backend, timeout=180)
        self._run([
            str(self.python), "-m", "app.cli.create_admin", "--username", username.strip(),
            "--display-name", display_name.strip() or "系统管理员", "--password-stdin",
        ], cwd=self.backend, input_text=admin_password + "\n")
        return "便携环境已初始化：本机数据库、结构和管理员均已就绪。现在可点击“启动 Web 服务”。"

    def start_database(self) -> None:
        if not (self.data / "PG_VERSION").is_file():
            raise RuntimeError("本机数据库尚未初始化，请先点击“初始化便携环境”。")
        self._check_database_address()
        deadline = time.monotonic() + READY_TIMEOUT_SECONDS
        status = hidden_run([str(self.pg_bin / "pg_ctl.exe"), "-D", str(self.data), "status"], capture_output=True, env=self._environment(), timeout=10)
        if status.returncode != 0:
            import socket
            try:
                with socket.create_connection(("127.0.0.1", DB_PORT), timeout=0.5):
                    raise RuntimeError("55432 端口被其他数据库占用，未接管。")
            except OSError:
                pass
            logs = self.root / "logs"
            logs.mkdir(parents=True, exist_ok=True)
            log_path = logs / "postgres.log"
            # pg_ctl launches postgres through cmd.exe on Windows. Its descendants
            # can inherit stdout/stderr handles, so capture_output=True would wait
            # for the database to stop even after pg_ctl itself has exited.
            result = hidden_run([
                str(self.pg_bin / "pg_ctl.exe"), "-D", str(self.data),
                "-l", str(log_path),
                "-o", f"-h 127.0.0.1 -p {DB_PORT}",
                "-t", str(READY_TIMEOUT_SECONDS), "-w", "start",
            ], env=self._environment(), stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=READY_TIMEOUT_SECONDS + 5)
            if result.returncode:
                detail = log_path.read_bytes()[-1024:].decode(
                    "mbcs" if os.name == "nt" else locale.getpreferredencoding(False), errors="replace"
                ).strip() if log_path.is_file() else "请查看 logs/postgres.log。"
                raise RuntimeError(f"便携 PostgreSQL 启动失败（退出码 {result.returncode}）：{detail}")
        self._wait_until_ready(deadline)

    def _wait_until_ready(self, deadline: float) -> None:
        command = [
            str(self.pg_bin / "pg_isready.exe"), "-h", "127.0.0.1",
            "-p", str(DB_PORT), "-U", "yinda_app", "-d", "postgres",
        ]
        while True:
            result = hidden_run(command, capture_output=True, env=self._environment(), timeout=5)
            if result.returncode == 0:
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("便携 PostgreSQL 在 60 秒内未就绪；请查看 logs/postgres.log。")
            time.sleep(min(0.75, remaining))

    def stop_database(self) -> None:
        if not (self.data / "PG_VERSION").is_file():
            return
        status = hidden_run([str(self.pg_bin / "pg_ctl.exe"), "-D", str(self.data), "status"], capture_output=True, env=self._environment(), timeout=10)
        if status.returncode == 0:
            self._run([str(self.pg_bin / "pg_ctl.exe"), "-D", str(self.data), "-m", "fast", "-w", "stop"])
