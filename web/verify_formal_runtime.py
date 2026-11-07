"""Opt-in frozen EXE acceptance using a pre-created dedicated test database.

Never installs a service. Database tests are restricted to loopback and yinda_console_* names.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx

from deployment.config import DeploymentConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--db-port", type=int, required=True)
    parser.add_argument("--web-port", type=int, default=58137)
    args = parser.parse_args()
    if not args.database.startswith("yinda_console_") or not args.root.is_absolute():
        raise SystemExit("只允许显式的 yinda_console_* 测试数据库及绝对测试目录。")
    config = DeploymentConfig(install_root=args.root / "program", data_root=args.root / "persistent",
        db_host="127.0.0.1", db_port=args.db_port, db_name=args.database,
        db_user=os.environ["YINDA_TEST_DB_USER"], db_password=os.environ["YINDA_TEST_DB_PASSWORD"],
        listen_host="127.0.0.1", web_port=args.web_port)
    config.save()
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    command = [str(args.server.resolve()), "--config", str(config.config_file)]
    password = "Runtime-Test-Admin-2026!"
    def call(action, payload=None):
        return subprocess.run([*command, action], input=json.dumps(payload) if payload else None,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, **options)
    checks = []
    init = call("--initialize", {"mode": "new", "username": "admin", "password": password})
    assert init.returncode == 0, init.stdout + init.stderr
    checks.append("frozen_initialize_postgresql17_alembic_admin")
    assert call("--check").returncode == 0
    checks.append("frozen_preflight")
    log = (args.root / "server.log").open("wb")
    process = None
    def start():
        p = subprocess.Popen([*command, "--serve"], stdout=log, stderr=log, stdin=subprocess.DEVNULL, **options)
        for _ in range(80):
            if p.poll() is not None:
                raise RuntimeError("冻结服务程序提前退出，请查看测试日志。")
            try:
                if httpx.get(config.local_url + "/api/v1/health", trust_env=False).status_code == 200:
                    return p
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
        raise RuntimeError("冻结服务程序未就绪。")
    try:
        process = start()
        checks.append("frozen_server_http_database_health")
        console = args.server.resolve().parents[2] / "console" / "YindaServerConsole.exe"
        assert console.is_file()
        gui = subprocess.run([str(console), "--home", str(config.install_root), "--smoke-test"],
                             timeout=30, **options)
        assert gui.returncode == 0
        assert httpx.get(config.local_url + "/api/v1/health", trust_env=False).status_code == 200
        checks.append("console_exit_does_not_stop_independent_web_process")
        with httpx.Client(base_url=config.local_url, trust_env=False) as client:
            assert client.get("/").status_code == 200
            assert client.get("/api/v1/health/database").json() == {"status": "ok"}
            assert client.get("/docs").status_code == 404
            assert client.get("/api/v1/projects").status_code == 401
            login = client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
            assert login.status_code == 200, login.text
            assert "secure" not in login.headers["set-cookie"].lower()
            assert "httponly" in login.headers["set-cookie"].lower()
            csrf = login.json()["csrf_token"]
            assert client.post("/api/v1/projects", json={"name": "Frozen acceptance", "status": "active"}).status_code == 403
            created = client.post("/api/v1/projects", headers={"X-CSRF-Token": csrf},
                                  json={"name": "Frozen acceptance", "status": "active"})
            assert created.status_code == 201, created.text
            project_uid = created.json()["project_uid"]
            checks.append("vue_spa_production_auth_cookie_csrf_project_creation")
        duplicate = call("--serve")
        assert duplicate.returncode != 0
        assert httpx.get(config.local_url + "/api/v1/health", trust_env=False).status_code == 200
        checks.append("duplicate_instance_rejected_original_survives")
        sentinel = config.data_root / "data/storage/runtime-retention.bin"
        sentinel.write_bytes(b"must-survive-restart")
        assert call("--stop").returncode == 0
        assert process.wait(timeout=40) == 0
        checks.append("windows_named_event_graceful_stop")
        process = start()
        with httpx.Client(base_url=config.local_url, trust_env=False) as client:
            login = client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
            assert login.status_code == 200
            projects = client.get("/api/v1/projects").json()
            assert any(row["project_uid"] == project_uid for row in projects)
        assert sentinel.read_bytes() == b"must-survive-restart"
        checks.append("project_admin_storage_survive_binary_restart")
        blocked = call("--initialize", {"mode": "new", "username": "other", "password": password})
        assert blocked.returncode != 0
        checks.append("frozen_reinitialize_refused")
    finally:
        if process and process.poll() is None:
            call("--stop")
            process.wait(timeout=40)
        log.close()
    (args.root / "acceptance.json").write_text(json.dumps({"passed": checks,
        "not_verified": ["SCM_install_start_stop_LocalService", "Windows_logoff", "other_LAN_computer_access"]}, indent=2), encoding="utf-8")
    print(json.dumps({"passed": checks}, indent=2))


if __name__ == "__main__":
    main()
