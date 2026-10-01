"""Production Web process management, independent of the GUI toolkit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse
from urllib.request import urlopen
from xml.etree import ElementTree

from backend.app.core.windows_subprocess import hidden_popen, hidden_run


TASK_NAME = "YindaWebCenter"
LOCAL_URL = "http://127.0.0.1:8000"


@dataclass(frozen=True)
class ConsolePaths:
    web_root: Path
    backend: Path
    frontend_dist: Path
    runtime: Path
    worker: Path
    python: Path
    pythonw: Path

    @property
    def portable(self) -> bool:
        root = self.web_root.parent / "runtime"
        return (root / "python" / "python.exe").is_file() and (root / "postgres" / "bin" / "initdb.exe").is_file()

    @classmethod
    def resolve(cls, web_root: Path | None = None) -> "ConsolePaths":
        if web_root is None:
            if getattr(sys, "frozen", False):
                web_root = Path(sys.executable).resolve().parent
                # Source builds keep the EXE in web/release; deployed
                # bundles place it directly in web_center.
                parent = web_root.parent
                if web_root.name.lower() == "release" and (parent / "backend").is_dir() and (parent / "server_worker.py").is_file():
                    web_root = parent
            else:
                web_root = Path(__file__).resolve().parent
        web_root = web_root.resolve()
        backend = web_root / "backend"
        venv = backend / ".venv" / "Scripts"
        portable = web_root.parent / "runtime" / "python"
        python_dir = venv if (venv / "python.exe").is_file() else portable
        return cls(
            web_root=web_root,
            backend=backend,
            frontend_dist=web_root / "frontend" / "dist",
            runtime=web_root / ".runtime",
            worker=web_root / "server_worker.py",
            python=python_dir / "python.exe",
            pythonw=python_dir / "pythonw.exe",
        )


def read_env_value(path: Path, key: str) -> str:
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.lstrip().startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip().upper() == key.upper():
            return value.strip().strip('"').strip("'")
    return ""


def health_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urlopen(url.rstrip("/") + "/api/v1/health", timeout=timeout) as response:
            return response.status == 200 and json.loads(response.read(4096)).get("status") == "ok"
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def database_ok() -> bool:
    try:
        with urlopen(LOCAL_URL + "/api/v1/health/database", timeout=2.0) as response:
            return response.status == 200 and json.loads(response.read(4096)).get("status") == "ok"
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def public_health(base_url: str) -> str:
    if not base_url:
        return "未配置公网访问地址"
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/") or parsed.username or parsed.password or parsed.query or parsed.fragment:
        return "公网访问地址应为 HTTPS 网站根地址"
    return "正常" if health_ok(base_url, timeout=3.0) else "异常"


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def tail(path: Path, lines: int = 100) -> str:
    if not path.is_file():
        return "暂无日志。"
    # Read only a bounded suffix of a potentially very large server log.
    with path.open("rb") as source:
        source.seek(0, 2)
        size = source.tell()
        source.seek(max(0, size - 131072))
        data = source.read()
    return "\n".join(data.decode("utf-8", errors="replace").splitlines()[-lines:])


class ServerManager:
    def __init__(self, paths: ConsolePaths | None = None, *, inspector=None, runner=None, popen=None, terminator=None):
        self.paths = paths or ConsolePaths.resolve()
        self.inspector = inspector or self._inspect_process
        self.runner = runner or subprocess.run
        self.popen = popen or subprocess.Popen
        self.terminator = terminator or self._terminate_process

    @property
    def pid_file(self) -> Path:
        return self.paths.runtime / "server.pid.json"

    def _log(self, message: str, name: str = "operations") -> None:
        log_dir = self.paths.runtime / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / f"{name}.log").open("a", encoding="utf-8") as log:
            log.write(f"{datetime.now().astimezone().isoformat()} {message}\n")

    def _inspect_process(self, pid: int) -> tuple[str, int] | None:
        if os.name != "nt":
            return None
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME)]
        kernel.GetProcessTimes.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(buffer))
            created = wintypes.FILETIME()
            exited = wintypes.FILETIME()
            kernel_time = wintypes.FILETIME()
            user_time = wintypes.FILETIME()
            if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
                return None
            if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel_time), ctypes.byref(user_time)):
                return None
            birth = (created.dwHighDateTime << 32) | created.dwLowDateTime
            return buffer.value, birth
        finally:
            kernel.CloseHandle(handle)

    def current_birth_token(self) -> int:
        identity = self._inspect_process(os.getpid())
        if identity is None:
            raise RuntimeError("无法读取当前进程身份。")
        return identity[1]

    def _allowed_pythonw(self) -> set[Path]:
        allowed = {self.paths.pythonw.resolve()}
        config = self.paths.pythonw.parent.parent / "pyvenv.cfg"
        if config.is_file():
            home = read_env_value(config, "home")
            if home:
                allowed.add((Path(home) / "pythonw.exe").resolve())
        return allowed

    def owned_pid(self) -> int | None:
        try:
            data = json.loads(self.pid_file.read_text(encoding="utf-8"))
            pid = int(data["pid"])
            if pid <= 0 or Path(data["worker"]).resolve() != self.paths.worker.resolve():
                return None
            identity = self.inspector(pid)
            if identity is None:
                return None
            executable, birth = identity
            if Path(executable).resolve() not in self._allowed_pythonw():
                return None
            if Path(data["executable"]).resolve() != Path(executable).resolve() or birth != int(data["birth_token"]):
                return None
            return pid
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def preflight(self) -> tuple[bool, str]:
        if not self.paths.python.is_file():
            return False, "缺少后端 Python 运行环境。"
        if not (self.paths.backend / ".env").is_file():
            return False, "缺少后端 .env 配置。"
        if not (self.paths.frontend_dist / "index.html").is_file():
            return False, "缺少正式管理页面 frontend/dist。"
        local_portable = self.paths.portable and read_env_value(self.paths.backend / ".env", "APP_ENV") == "development"
        check_module = "app.cli.portable_check" if local_portable else "app.cli.production_check"
        result = hidden_run(
            [str(self.paths.python), "-m", check_module],
            runner=self.runner,
            cwd=self.paths.backend, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        messages = [line for line in result.stdout.splitlines() if line.startswith(("BLOCKER:", "WARNING:", "PASS:"))]
        self._log(f"运行环境预检退出码 {result.returncode}；" + "；".join(messages), "preflight")
        blockers = [line for line in messages if line.startswith("BLOCKER:")]
        (self.paths.runtime / "preflight.status.json").parent.mkdir(parents=True, exist_ok=True)
        (self.paths.runtime / "preflight.status.json").write_text(
            json.dumps({"ok": result.returncode == 0 and not blockers, "checked_at": datetime.now().isoformat()}),
            encoding="utf-8",
        )
        return result.returncode == 0 and not blockers, "\n".join(blockers or messages[-5:])

    def start(self) -> str:
        if self.owned_pid() is not None:
            return "Web 服务已运行，不会重复启动。"
        if port_open(8000):
            raise RuntimeError("8000 端口由非本控制台管理的进程占用，请人工检查。")
        if self.paths.portable:
            from portable_runtime import PortableRuntime
            PortableRuntime(self.paths.web_root).start_database()
        ok, reason = self.preflight()
        if not ok:
            raise RuntimeError("运行环境预检未通过：\n" + reason)
        if not self.paths.pythonw.is_file() or not self.paths.worker.is_file():
            raise RuntimeError("缺少隐藏运行所需的 Python 或服务入口。")
        self.paths.runtime.mkdir(parents=True, exist_ok=True)
        process = hidden_popen(
            [str(self.paths.pythonw), str(self.paths.worker)],
            popen=self.popen,
            cwd=self.paths.backend, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        self._log(f"启动服务入口进程 PID {process.pid}")
        for _ in range(30):
            owned = self.owned_pid()
            if owned is not None and health_ok(LOCAL_URL, timeout=0.5):
                self._log(f"Web 服务 PID {owned} 已就绪")
                return f"Web 服务已启动（PID {owned}）。"
            if process.poll() is not None:
                break
            time.sleep(0.5)
        raise RuntimeError("Web 服务启动超时或已退出，请查看 server.log 与 preflight.log。")

    def stop(self) -> str:
        pid = self.owned_pid()
        if pid is None:
            if port_open(8000):
                raise RuntimeError("8000 端口由非本控制台管理的进程占用，不会停止该进程。")
            return "Web 服务已停止。"
        if self.owned_pid() != pid or not self.terminator(pid):
            raise RuntimeError("停止服务失败，请以管理员身份运行控制台并查看运行日志。")
        self._log(f"停止 Web 服务进程 PID {pid}")
        return "Web 服务已停止。"

    def initialize_portable(self, username: str, display_name: str, password: str) -> str:
        if not self.paths.portable:
            raise RuntimeError("当前目录不是完整的 Windows 便携包。")
        if port_open(8000):
            raise RuntimeError("请先停止 Web 服务，再初始化或升级数据库结构。")
        from portable_runtime import PortableRuntime
        return PortableRuntime(self.paths.web_root).initialize(username, display_name, password)

    def stop_all(self) -> str:
        if not self.paths.portable:
            raise RuntimeError("停止全部仅供便携包使用。")
        self.stop()
        from portable_runtime import PortableRuntime
        PortableRuntime(self.paths.web_root).stop_database()
        return "Web 服务与便携 PostgreSQL 均已停止。"

    @staticmethod
    def _terminate_process(pid: int) -> bool:
        if os.name != "nt":
            return False
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.TerminateProcess.restype = wintypes.BOOL
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x0001 | 0x00100000, False, pid)
        if not handle:
            return False
        try:
            if not kernel.TerminateProcess(handle, 0):
                return False
            kernel.WaitForSingleObject(handle, 5000)
            return True
        finally:
            kernel.CloseHandle(handle)

    def restart(self) -> str:
        self.stop()
        for _ in range(20):
            if not port_open(8000):
                break
            time.sleep(0.25)
        return self.start()

    def backup(self) -> str:
        started = time.monotonic()
        if self.paths.portable:
            from portable_runtime import PortableRuntime
            PortableRuntime(self.paths.web_root).start_database()
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["LC_MESSAGES"] = "C"
        env["LANG"] = "C"
        env["PGCLIENTENCODING"] = "UTF8"
        portable_pg_bin = self.paths.web_root.parent / "runtime" / "postgres" / "bin"
        if (portable_pg_bin / "pg_dump.exe").is_file():
            env["PATH"] = str(portable_pg_bin) + os.pathsep + env.get("PATH", "")
        result = hidden_run(
            [str(self.paths.python), "-m", "app.cli.backup_web_center"],
            runner=self.runner,
            cwd=self.paths.backend, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=3600,
            env=env,
        )
        success_line = next((line for line in result.stdout.splitlines() if line.startswith("备份完成：")), "")
        self._log(f"备份退出码 {result.returncode}；{success_line or '未生成备份'}", "backup")
        if result.returncode or not success_line:
            raise RuntimeError("备份失败，请查看备份日志并确认 pg_dump 和磁盘空间。")
        return f"{success_line}\n完成时间：{datetime.now():%Y-%m-%d %H:%M:%S}\n耗时：{time.monotonic() - started:.1f} 秒"

    def status(self) -> dict[str, str]:
        public_url = read_env_value(self.paths.backend / ".env", "PUBLIC_BASE_URL")
        pid = self.owned_pid()
        disk = shutil.disk_usage(self.paths.web_root)
        db_port = int(read_env_value(self.paths.backend / ".env", "DB_PORT") or ("55432" if self.paths.portable else "5432"))
        service_name = read_env_value(self.paths.backend / ".env", "POSTGRES_SERVICE_NAME")
        service = "便携数据库" if self.paths.portable else "未指定"
        if service_name and os.name == "nt":
            query = hidden_run(["sc.exe", "query", service_name], runner=self.runner, capture_output=True, text=True, timeout=8)
            service = "运行中" if query.returncode == 0 and "RUNNING" in query.stdout else "已停止或未找到"
        try:
            preflight = json.loads((self.paths.runtime / "preflight.status.json").read_text(encoding="utf-8"))
            preflight_status = "通过" if preflight["ok"] else "未通过"
        except (OSError, ValueError, KeyError):
            preflight_status = "尚未执行"
        try:
            migration = hidden_run(
                [str(self.paths.python), "-m", "alembic", "current", "--check-heads"],
                runner=self.runner,
                cwd=self.paths.backend, capture_output=True, text=True, timeout=15,
                encoding="utf-8", errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            alembic = "最新" if migration.returncode == 0 else "未到最新或无法检查"
            database_connected = migration.returncode == 0 or "not on current head" in (migration.stdout + migration.stderr).lower() or database_ok()
        except (OSError, subprocess.TimeoutExpired):
            alembic = "无法检查"
            database_connected = database_ok()
        return {
            "postgresql": "连接端口正常" if port_open(db_port) else "连接端口异常",
            "postgres_service": service,
            "db_port": str(db_port),
            "database": "连接正常" if database_connected else "连接异常或无法检查",
            "web": "运行正常" if pid and health_ok(LOCAL_URL) else "已停止" if not port_open(8000) else "异常或非本项目进程",
            "pid": str(pid or "—"),
            "public": public_health(public_url),
            "public_url": public_url,
            "app_env": read_env_value(self.paths.backend / ".env", "APP_ENV") or "未配置",
            "frontend": "已就绪" if (self.paths.frontend_dist / "index.html").is_file() else "缺失",
            "alembic": alembic,
            "preflight": preflight_status,
            "storage": self._writable(self.paths.backend / "storage"),
            "backups": self._writable(self.paths.backend / "backups"),
            "disk": f"{disk.free / 1024**3:.1f} GB",
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    @staticmethod
    def _writable(path: Path) -> str:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / f".console-write-{os.getpid()}"
            probe.write_text("ok", encoding="ascii")
            probe.unlink()
            return "可写"
        except OSError:
            return "不可写"

    def install_autostart(self) -> str:
        if self.paths.portable:
            raise RuntimeError("便携版 PostgreSQL 未注册系统服务；请开机后打开控制台启动。")
        if os.name != "nt":
            raise RuntimeError("开机自启仅支持 Windows。")
        if not self.paths.pythonw.is_file() or not self.paths.worker.is_file():
            raise RuntimeError("缺少服务运行文件。")
        existing = hidden_run(
            ["schtasks.exe", "/query", "/tn", TASK_NAME, "/xml"],
            runner=self.runner, capture_output=True, text=True, timeout=10,
        )
        if existing.returncode == 0:
            try:
                task = ElementTree.fromstring(existing.stdout)
                command_path = next(node.text for node in task.iter() if node.tag.endswith("}Command") or node.tag == "Command")
                arguments = next(node.text or "" for node in task.iter() if node.tag.endswith("}Arguments") or node.tag == "Arguments")
                if Path(command_path).resolve() != self.paths.pythonw.resolve() or str(self.paths.worker.resolve()).casefold() not in arguments.casefold():
                    raise RuntimeError("已有同名开机任务属于其他程序，未修改该任务。")
            except (ElementTree.ParseError, StopIteration, TypeError, ValueError) as exc:
                raise RuntimeError("无法核验已有同名开机任务，未修改该任务。") from exc
        def quote_ps(value: str) -> str:
            return "'" + value.replace("'", "''") + "'"
        task_command = "Set-ScheduledTask" if existing.returncode == 0 else "Register-ScheduledTask"
        command = (
            f"$action=New-ScheduledTaskAction -Execute {quote_ps(str(self.paths.pythonw))} "
            f"-Argument {quote_ps('"' + str(self.paths.worker) + '"')} -WorkingDirectory {quote_ps(str(self.paths.backend))}; "
            "$trigger=New-ScheduledTaskTrigger -AtStartup; "
            "$principal=New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest; "
            "$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable "
            "-ExecutionTimeLimit (New-TimeSpan -Seconds 0); "
            f"{task_command} -TaskName '{TASK_NAME}' -Action $action -Trigger $trigger "
            "-Principal $principal -Settings $settings | Out-Null"
        )
        result = hidden_run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            runner=self.runner, capture_output=True, text=True, timeout=30,
        )
        if result.returncode:
            raise RuntimeError("设置开机自启失败，请以管理员身份运行控制台。")
        self._log("已注册 Windows 开机启动任务")
        return "已设置开机自动启动。"
