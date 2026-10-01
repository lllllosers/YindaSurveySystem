"""Hidden, detached Web entrypoint used by the server console and startup task."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

from server_console_core import ConsolePaths, ServerManager, port_open, read_env_value


def _exclusive_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    handle.seek(0)
    handle.write(b"0")
    handle.flush()
    handle.seek(0)
    if os.name == "nt":
        import msvcrt
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            handle.close()
            return None
    else:
        import fcntl
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return None
    return handle


def main() -> int:
    paths = ConsolePaths.resolve(Path(__file__).resolve().parent)
    paths.runtime.mkdir(parents=True, exist_ok=True)
    lock = _exclusive_lock(paths.runtime / "server.lock")
    if lock is None:
        return 0
    log_path = paths.runtime / "logs" / "server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", buffering=1) as log:
        sys.stdout = log
        sys.stderr = log
        try:
            manager = ServerManager(paths)
            # PostgreSQL Windows Service can take a little longer to start at boot.
            db_port = int(read_env_value(paths.backend / ".env", "DB_PORT") or "5432")
            for _ in range(24):
                if port_open(db_port):
                    break
                time.sleep(5)
            ok, reason = manager.preflight()
            if not ok:
                print(f"生产环境预检未通过：{reason}", flush=True)
                return 1
            pid_data = {
                "pid": os.getpid(),
                "worker": str(paths.worker),
                "executable": manager._inspect_process(os.getpid())[0],
                "birth_token": manager.current_birth_token(),
                "started_at": time.time(),
            }
            temporary = paths.runtime / f"server.pid.{os.getpid()}.tmp"
            temporary.write_text(json.dumps(pid_data), encoding="utf-8")
            temporary.replace(manager.pid_file)
            os.chdir(paths.backend)
            sys.path.insert(0, str(paths.backend))
            print(f"Web 服务启动，PID {os.getpid()}", flush=True)
            import uvicorn
            uvicorn.run("app.main:app", host="127.0.0.1", port=8000, proxy_headers=False, access_log=False)
            return 0
        except Exception:
            print("Web 服务启动或运行失败；请检查预检与环境配置。", flush=True)
            return 1
        finally:
            try:
                data = json.loads(manager.pid_file.read_text(encoding="utf-8"))
                if data.get("pid") == os.getpid():
                    manager.pid_file.unlink()
            except (OSError, ValueError, NameError):
                pass
            lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
