"""Opt-in integration against a newly created, dedicated test database only."""
import json
import os
from pathlib import Path
import sys

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from deployment.config import DeploymentConfig
from deployment.database import connect_engine, initialize, preflight


@pytest.mark.skipif(os.environ.get("YINDA_CONSOLE_INTEGRATION") != "1", reason="requires isolated PostgreSQL 17")
def test_real_initialization_continuation_preserves_database_and_storage(tmp_path):
    name = os.environ.get("YINDA_CONSOLE_INTEGRATION_DB", "")
    assert name.startswith("yinda_console_integration_")
    config = DeploymentConfig(install_root=tmp_path / "program", data_root=tmp_path / "persistent",
        db_host="127.0.0.1", db_port=int(os.environ["DB_PORT"]), db_name=name,
        db_user=os.environ["DB_USER"], db_password=os.environ["DB_PASSWORD"])
    config.save()
    initialize(config, "new", "admin", "Only-Test-Password-2026!")
    assert "正常" in preflight(config)
    engine = connect_engine(config)
    try:
        with engine.begin() as connection:
            initial = connection.execute(text("SELECT user_uid,password_hash FROM users WHERE username='admin'")).one()
            connection.execute(text("CREATE TABLE deployment_preservation_probe (value TEXT)"))
            connection.execute(text("INSERT INTO deployment_preservation_probe VALUES ('keep')"))
        sentinel = config.storage_dir / "probe.bin"
        sentinel.write_bytes(b"business-file-must-survive")
        with pytest.raises(RuntimeError, match="已有"):
            initialize(config, "new", "different", "Other-Test-Password-2026!")
        initialize(config, "continue", "admin", "Other-Test-Password-2026!")
        assert sentinel.read_bytes() == b"business-file-must-survive"
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT value FROM deployment_preservation_probe")) == "keep"
            assert connection.execute(text("SELECT user_uid,password_hash FROM users WHERE username='admin'")).one() == initial
        assert json.loads(config.state_file.read_text())["phase"] == "ready"
    finally:
        engine.dispose()
