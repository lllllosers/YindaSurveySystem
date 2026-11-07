"""Opt-in tests restricted to the explicitly provisioned local test cluster."""
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from deployment.config import DeploymentConfig
from deployment.database import initialize, preflight
from deployment.provision import create_dedicated_database


@pytest.mark.skipif(os.environ.get("YINDA_UNIFIED_TEST_CLUSTER") != "1", reason="explicit isolated PG17 cluster required")
def test_controlled_provision_initialization_backup_and_no_overwrite(tmp_path):
    token = uuid4().hex[:8]
    config = DeploymentConfig(tmp_path / "program", tmp_path / "persistent", db_port=int(os.environ["DB_PORT"]),
        db_name="yinda_console_provision_" + token, db_user="yinda_console_user_" + token,
        db_password="Only-App-Test-Password-2026!", pg_bin=os.environ["YINDA_TEST_PG_BIN"])
    credentials = {"username": os.environ["DB_USER"], "password": "Only-Temporary-Admin-Secret-2026!", "create_dedicated": True}
    config.save()
    assert "已创建" in create_dedicated_database(config, credentials)
    assert "未更改" in create_dedicated_database(config, credentials)
    with psycopg.connect(host="127.0.0.1", port=config.db_port, user=credentials["username"], dbname="postgres") as connection:
        assert connection.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s", (config.db_user,)).fetchone() == (False, False, False, False, False)
    other = DeploymentConfig(tmp_path / "other-program", tmp_path / "other-persistent", db_port=config.db_port,
        db_name=config.db_name, db_user=config.db_user, db_password=config.db_password)
    with pytest.raises(RuntimeError, match="已存在"):
        create_dedicated_database(other, credentials)
    initialize(config, "new", "admin", "Only-Web-Test-Password-2026!")
    assert "正常" in preflight(config)
    with pytest.raises(RuntimeError, match="已有部署"):
        create_dedicated_database(config, credentials)
    storage = config.storage_dir
    (storage / "test-result.ydresult").write_bytes(b"isolated-test-result")
    server = Path(__file__).resolve().parents[2] / "server_entry.py"
    command = [sys.executable, str(server), "--config", str(config.config_file)]
    backup = subprocess.run(command + ["--backup"], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert backup.returncode == 0, backup.stdout + backup.stderr
    path = Path(backup.stdout.strip().removeprefix("备份完成："))
    assert (path / "storage/test-result.ydresult").read_bytes() == b"isolated-test-result"
    assert (path / "database.dump").read_bytes().startswith(b"PGDMP")
    assert json.loads((path / "manifest.json").read_text(encoding="utf-8"))["complete"]
    listing = subprocess.run([str(Path(config.pg_bin) / "pg_restore.exe"), "--list", str(path / "database.dump")], capture_output=True, timeout=30)
    assert listing.returncode == 0 and b"users" in listing.stdout
    diagnostic = subprocess.run(command + ["--diagnose"], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert diagnostic.returncode == 0, diagnostic.stdout
    assert json.loads(diagnostic.stdout)["ok"], diagnostic.stdout
    for file in (config.data_root / "config").glob("*"):
        assert credentials["password"] not in file.read_text(encoding="utf-8")
