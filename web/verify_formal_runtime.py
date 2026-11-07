"""Opt-in frozen EXE acceptance using a pre-created dedicated test database.

Never installs a service. Database tests are restricted to loopback and yinda_console_* names.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import httpx
from openpyxl import load_workbook
import psycopg
from psycopg.types.json import Jsonb

from deployment.config import DeploymentConfig
from branding import PRODUCT_EXE
from server_console_core import lan_ipv4
from shared.forms.engineering.registry import get_engineering_form_definitions


def verify_business_resources(client, config, root, project_uid):
    """Seed only this guarded test DB, then export through the frozen HTTP server."""
    snapshot = client.get("/api/v1/master-data/snapshot")
    assert snapshot.status_code == 200, snapshot.text
    snapshot = snapshot.json()
    assert snapshot["offices"] and snapshot["canals"]
    office = snapshot["offices"][0]["stable_uid"]
    canal = snapshot["canals"][0]["stable_uid"]
    asset_uid = uuid4().hex
    definitions = get_engineering_form_definitions()
    assert len(definitions) == 14
    rows = []
    with psycopg.connect(host=config.db_host, port=config.db_port, dbname=config.db_name,
                        user=config.db_user, password=config.db_password) as connection:
        connection.execute("""INSERT INTO central_engineering_assets
            (engineering_asset_uid,project_uid,asset_name,business_code,revision_no,content_sha256,payload_json,current_submission_uid)
            VALUES (%s,%s,%s,%s,1,%s,%s,%s)""",
            (asset_uid, project_uid, "冻结交付测试工程", "FROZEN-001", "0"*64,
             Jsonb({"start_stake_text": "1+000", "end_stake_text": "1+100"}), "a"*32))
        for definition in definitions:
            uid = uuid4().hex
            record_data = {field.key: "冻结验收值" for field in definition.fields}
            record_data.update(start_stake="1+000", end_stake="1+100")
            connection.execute("""INSERT INTO central_survey_records
                (survey_record_uid,engineering_asset_uid,project_uid,survey_batch_uid,form_code,
                organization_unit_uid,canal_unit_uid,revision_no,content_sha256,payload_json,current_submission_uid)
                VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s)""",
                (uid, asset_uid, project_uid, "b"*32, definition.form_code, office, canal, "0"*64,
                 Jsonb({"record_data": record_data, "overall_grade": "B", "survey_comment": "冻结资源验证"}), "a"*32))
            rows.append((uid, definition))
    exported = root / "exports"
    exported.mkdir()
    for uid, definition in rows:
        response = client.get(f"/api/v1/central-records/{uid}/original-form.xlsx")
        assert response.status_code == 200, (definition.form_code, response.text[:500])
        assert response.content.startswith(b"PK")
        workbook = load_workbook(BytesIO(response.content))
        try:
            export = definition.original_form_export_definition
            sheet = workbook[export.sheet_name]
            assert sheet[export.conclusion_binding.overall_grade_cell].value == "B"
            assert sheet[export.conclusion_binding.survey_comment_cell].value == "冻结资源验证"
        finally:
            workbook.close()
        (exported / (definition.form_code + ".xlsx")).write_bytes(response.content)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--db-port", type=int, required=True)
    parser.add_argument("--web-port", type=int, default=58137)
    parser.add_argument("--create-database", action="store_true")
    parser.add_argument("--pg-bin", default="")
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if not args.database.startswith("yinda_console_") or not args.root.is_absolute():
        raise SystemExit("只允许显式的 yinda_console_* 测试数据库及绝对测试目录。")
    config = DeploymentConfig(install_root=args.root / "program", data_root=args.root / "data",
        db_host="127.0.0.1", db_port=args.db_port, db_name=args.database,
        db_user=args.database + "_app" if args.create_database else os.environ["YINDA_TEST_DB_USER"],
        db_password="Frozen-App-Test-Password-2026!" if args.create_database else os.environ["YINDA_TEST_DB_PASSWORD"],
        listen_host="0.0.0.0" if args.lan else "127.0.0.1", web_port=args.web_port, pg_bin=args.pg_bin,
        allowed_hosts=",".join(["127.0.0.1", "localhost", *(lan_ipv4() if args.lan else [])]))
    config.save()
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    command = [str(args.server.resolve()), "--config", str(config.config_file)]
    password = "Pass1234"  # The documented minimum must initialize and log in.
    def call(action, payload=None):
        return subprocess.run([*command, action], input=json.dumps(payload) if payload else None,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, **options)
    checks = []
    package = args.server.resolve().parents[2]
    manifest = json.loads((package / "build-manifest.json").read_text(encoding="utf-8"))
    assert manifest["gui_entry"] == "launcher.py" and manifest["operations_entry"] == "server_console_core.py"
    checks.append("single_gui_and_operations_entry_in_manifest")
    if args.create_database:
        provision = call("--provision", {"username": os.environ["YINDA_TEST_DB_USER"],
            "password": os.environ["YINDA_TEST_DB_PASSWORD"], "create_dedicated": True})
        assert provision.returncode == 0, provision.stdout + provision.stderr
        checks.append("frozen_controlled_dedicated_database_and_user_creation")
    init = call("--initialize", {"mode": "new", "username": "admin", "password": password})
    assert init.returncode == 0, init.stdout + init.stderr
    checks.append("frozen_initialize_postgresql17_alembic_admin")
    assert call("--check").returncode == 0
    checks.append("frozen_preflight")
    diagnostic = call("--diagnose")
    assert diagnostic.returncode == 0 and json.loads(diagnostic.stdout)["ok"], diagnostic.stdout
    checks.append("frozen_full_environment_diagnostics")
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
        console = args.server.resolve().parents[2] / PRODUCT_EXE
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
            assert verify_business_resources(client, config, args.root, project_uid) == 14
            checks.append("frozen_shared_master_data_and_fourteen_real_excel_http_exports")
        if args.lan:
            for address in lan_ipv4():
                assert httpx.get(f"http://{address}:{config.web_port}/api/v1/health", trust_env=False).status_code == 200
            checks.append("lan_listen_and_server_own_ipv4_http_only_not_peer_acceptance")
        duplicate = call("--serve")
        assert duplicate.returncode != 0
        assert httpx.get(config.local_url + "/api/v1/health", trust_env=False).status_code == 200
        checks.append("duplicate_instance_rejected_original_survives")
        sentinel = config.storage_dir / "runtime-retention.bin"
        sentinel.write_bytes(b"must-survive-restart")
        assert call("--stop").returncode == 0
        assert process.wait(timeout=40) == 0
        checks.append("windows_named_event_graceful_stop")
        backup = call("--backup")
        assert backup.returncode == 0, backup.stdout + backup.stderr
        backup_path = Path(backup.stdout.strip().removeprefix("备份完成："))
        assert (backup_path / "database.dump").read_bytes().startswith(b"PGDMP")
        assert (backup_path / "storage/runtime-retention.bin").read_bytes() == b"must-survive-restart"
        assert json.loads((backup_path / "manifest.json").read_text(encoding="utf-8"))["complete"]
        checks.append("frozen_database_and_storage_backup_with_completion_marker")
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
        "not_verified": ["SCM_install_start_stop_LocalService", "SCM_backup_stop_resume", "Windows_logoff", "Windows_reboot_automatic_start", "other_LAN_computer_access"]}, indent=2), encoding="utf-8")
    print(json.dumps({"passed": checks}, indent=2))


if __name__ == "__main__":
    main()
