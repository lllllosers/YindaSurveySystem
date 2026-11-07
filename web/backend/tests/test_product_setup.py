import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import sys
import json
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from deployment.config import DeploymentConfig
from deployment import installer
from deployment.installer import DeploymentError, STEPS
from server_setup import SetupWizard, network_values


@pytest.fixture
def config(tmp_path):
    return DeploymentConfig(tmp_path / "program", tmp_path / "data", db_password="unique-generated-test-secret")


def test_default_wizard_hides_technical_fields_and_uses_flat_data(config, monkeypatch):
    app = QApplication.instance() or QApplication([])
    import server_setup
    monkeypatch.setattr(server_setup, "installation_status", lambda *a: {"installed": True, "pg_bin": "", "detail": "test PG17"})
    wizard = SetupWizard(config.install_root, None, ["192.168.1.20"])
    try:
        assert wizard.inputs["data_root"].text() == str(config.install_root / "data")
        assert wizard.inputs["db_name"].text() == "yinda_web_center"
        assert wizard.inputs["db_user"].text() == "yinda_web_user"
        assert len(wizard.inputs["db_password"].text()) >= 32
        assert all(not toggle.isChecked() and group.isHidden() for toggle, group in wizard.advanced_sections)
        assert wizard.network_buttons["lan"].isChecked()
        assert not wizard.network_buttons["public"].isEnabled()
        wizard.inputs["db_admin_password"].setText("temporary-manager-secret")
        wizard.inputs["admin_password"].setText("Pass1234")
        wizard.inputs["repeat_password"].setText("Pass1234")
        wizard.accept()
        assert wizard.result() == wizard.DialogCode.Accepted
        assert wizard.config.data_layout == "flat"
        assert wizard.config.storage_dir == config.install_root / "data/storage"
        assert wizard.config.listen_host == "0.0.0.0"
        assert "192.168.1.20" in wizard.config.allowed_hosts
        assert wizard.password == "Pass1234"
        assert wizard.database_admin["password"] == "temporary-manager-secret"
    finally:
        wizard.clear_secrets()
        wizard.close()
        app.processEvents()


def test_network_modes_are_production_http_without_public_exposure():
    assert network_values("local", ["192.168.1.20"]) == {"listen_host": "127.0.0.1", "allowed_hosts": "127.0.0.1,localhost"}
    assert network_values("lan", ["192.168.1.20"])["listen_host"] == "0.0.0.0"
    with pytest.raises(ValueError, match="HTTPS"):
        network_values("public", [])


def test_existing_layout_load_is_legacy_and_new_layout_is_flat(config):
    config.save()
    assert DeploymentConfig.load(config.install_root).storage_dir == config.data_root / "storage"
    text = config.config_file.read_text(encoding="utf-8")
    config.config_file.write_text("\n".join(line for line in text.splitlines() if not line.startswith("DATA_LAYOUT=")), encoding="utf-8")
    existing = DeploymentConfig.load(config.install_root)
    assert existing.data_layout == "legacy"
    assert existing.storage_dir == config.data_root / "data/storage"


@pytest.mark.parametrize("fail_step", [None, "postgres", "install"])
def test_pipeline_has_step_feedback_and_no_later_actions_after_failure(config, monkeypatch, fail_step):
    if sys.platform != "win32":
        pytest.skip("Windows setup")
    events, actions = [], []
    monkeypatch.setattr(installer.ctypes.windll.shell32, "IsUserAnAdmin", lambda: True)
    monkeypatch.setattr(installer, "install_payload", lambda *a: None)
    monkeypatch.setattr(installer, "run", lambda *a, **k: SimpleNamespace(returncode=0))
    monkeypatch.setattr(installer, "health", lambda *a: True)
    class Service:
        def __init__(self, cfg): pass
        def status(self): return {"state": "absent", "owned": False}
        def legacy_task(self): return False
        def server_action(self, action, **kwargs):
            actions.append(action)
            if fail_step == "postgres" and action == "--postgres-check":
                raise RuntimeError("测试数据库连接失败")
            return "test operation complete"
        def install(self):
            actions.append("install")
            if fail_step == "install":
                raise RuntimeError("测试服务安装失败")
            return "test service installed"
        def control(self, action): actions.append(action); return "test started"
    monkeypatch.setattr(installer, "ServiceManager", Service)
    callback = lambda *row: events.append(row)
    if fail_step:
        with pytest.raises(DeploymentError) as error:
            installer.deploy(config.install_root, config, "new", "admin", "Pass1234", database_admin={"username": "manager", "password": "do-not-store"}, progress=callback)
        assert error.value.step == fail_step
        assert events[-1][0:2] == (fail_step, "failed")
        assert "start" not in actions
    else:
        result = installer.deploy(config.install_root, config, "new", "admin", "Pass1234", progress=callback)
        assert result["message"] == "Web Center 已成功启动"
        assert [row[0] for row in events if row[1] == "complete"] == [step[0] for step in STEPS]
    assert "do-not-store" not in (config.data_root / "logs/install.log").read_text(encoding="utf-8")
    assert "do-not-store" not in config.config_file.read_text(encoding="utf-8")


def test_no_admin_reports_environment_failure_without_touching_database(config, monkeypatch):
    if sys.platform != "win32":
        pytest.skip("Windows setup")
    monkeypatch.setattr(installer.ctypes.windll.shell32, "IsUserAnAdmin", lambda: False)
    monkeypatch.setattr(installer, "ServiceManager", lambda *a: pytest.fail("must not contact DB or SCM"))
    events = []
    with pytest.raises(DeploymentError, match="管理员权限"):
        installer.deploy(config.install_root, config, "new", "admin", "Pass1234", progress=lambda *row: events.append(row))
    assert events[-1][0:2] == ("environment", "failed")
    assert not config.config_file.exists()
