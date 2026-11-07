"""Frozen Web Server CLI. Contains no GUI, interpreter or external command dependency."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import threading

WEB = Path(__file__).resolve().parent
sys.path.insert(0, str(WEB))
sys.path.insert(0, str(WEB / "backend"))


def serve(config) -> int:
    from deployment.database import preflight
    from deployment.service import event_name, port_available
    import uvicorn
    from app.core.config import settings
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateEventW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    mutex = kernel.CreateMutexW(None, False, event_name(config, "instance"))
    if not mutex or ctypes.get_last_error() == 183:
        if mutex:
            kernel.CloseHandle(mutex)
        raise RuntimeError("此部署已有运行实例。")
    stop = None
    try:
        preflight(config)
        if not (settings.frontend_dist / "index.html").is_file():
            raise RuntimeError("缺少正式 Vue 页面。")
        if not port_available(config.listen_host, config.web_port):
            raise RuntimeError("监听端口已被其他程序占用。")
        stop = kernel.CreateEventW(None, True, False, event_name(config, "stop"))
        if not stop:
            raise RuntimeError("无法创建服务停止事件。")
        from app.main import app
        server = uvicorn.Server(uvicorn.Config(app, host=config.listen_host, port=config.web_port,
            proxy_headers=False, workers=1, timeout_graceful_shutdown=30))
        def watch():
            while not finished.is_set():
                if kernel.WaitForSingleObject(stop, 250) == 0:
                    server.should_exit = True
                    return
        finished = threading.Event()
        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        try:
            server.run()
        finally:
            finished.set()
            watcher.join(2)
        return 0 if server.started else 1
    finally:
        if stop:
            kernel.CloseHandle(stop)
        kernel.CloseHandle(mutex)


def stop_server(config) -> int:
    from deployment.service import event_name
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenEventW.restype = wintypes.HANDLE
    kernel.SetEvent.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenEventW(2, False, event_name(config, "stop"))
    if not handle:
        return 0  # Already stopped, WinSW handles failed-start cleanup.
    try:
        return 0 if kernel.SetEvent(handle) else 1
    finally:
        kernel.CloseHandle(handle)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    for action in ("serve", "stop", "check", "initialize", "smoke-test", "diagnose", "status", "backup", "provision"):
        group.add_argument("--" + action, action="store_true")
    args = parser.parse_args()
    if args.smoke_test:
        # Import real binary dependencies and resource readers without any database connection.
        os.environ["DB_PASSWORD"] = "smoke-test-only-secret"
        os.environ["APP_ENV"] = "test"
        from app.main import app
        from app.db.base import Base
        from app.core.config import settings
        from deployment.database import migration_config
        from alembic.script import ScriptDirectory
        from app.services.master_data_service import load_contract
        from app.services.original_form_export import REPOSITORY_ROOT
        assert (settings.frontend_dist / "index.html").is_file()
        assert (REPOSITORY_ROOT / "templates" / "excel").is_dir()
        assert load_contract()[0]["departments"]
        assert ScriptDirectory.from_config(migration_config()).get_current_head()
        print("Web Server binary/resources smoke test passed.")
        return 0
    from deployment.config import DeploymentConfig, safe_error
    try:
        if not args.config or not args.config.is_absolute() or not args.config.is_file():
            raise ValueError("缺少正式运行配置。")
        from dotenv import dotenv_values
        values = dotenv_values(args.config, interpolate=False)
        # A service always uses its own file, never ambient developer DB_* or cwd .env.
        from deployment.config import DeploymentConfig
        for key in ("APP_ENV", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DATA_ROOT",
                    "SESSION_COOKIE_SECURE", "ENABLE_HSTS", "TRANSPORT_MODE", "ALLOWED_HOSTS", "REGISTRATION_MODE"):
            os.environ.pop(key, None)
        os.environ.update({k: v for k, v in values.items() if v is not None})
        os.environ["YINDA_CONFIG_FILE"] = str(args.config)
        config = DeploymentConfig.load(Path(values["INSTALL_ROOT"])) if "INSTALL_ROOT" in values else DeploymentConfig(
            install_root=Path(sys.executable).resolve().parents[2] if getattr(sys, "frozen", False) else WEB,
            data_root=Path(values["DATA_ROOT"]), **{k: (int(values[k.upper()]) if k in {"web_port", "db_port"} else values[k.upper()])
                for k in DeploymentConfig.__dataclass_fields__ if k not in {"install_root", "data_root"} and k.upper() in values})
        config.validate()
        if args.stop:
            return stop_server(config)
        from deployment.database import initialize, preflight
        if args.check:
            print(preflight(config))
        elif args.status:
            from deployment.diagnostics import database_status
            print(json.dumps(database_status(config)))
        elif args.diagnose:
            from deployment.diagnostics import diagnose
            print(json.dumps(diagnose(config), ensure_ascii=False))
        elif args.backup:
            preflight(config)
            from app.cli.backup_web_center import create_backup
            print(f"备份完成：{create_backup()}")
        elif args.provision:
            from deployment.provision import create_dedicated_database
            print(create_dedicated_database(config, json.loads(sys.stdin.read(16384))))
        elif args.initialize:
            payload = json.loads(sys.stdin.read(16384))
            print(initialize(config, payload["mode"], payload["username"], payload["password"]))
        else:
            return serve(config)
        return 0
    except Exception as exc:
        print(safe_error(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
