"""Regression coverage for the original console's capabilities on the formal core."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import server_console_core as core
from deployment.config import DeploymentConfig


@pytest.fixture
def manager(tmp_path):
    config = DeploymentConfig(tmp_path / "program", tmp_path / "persistent", db_password="test-only-password")
    config.ensure_directories()
    config.save()
    return core.ServerManager(config.install_root)


def test_all_service_actions_delegate_to_one_service_adapter(manager, monkeypatch):
    calls = []
    monkeypatch.setattr(core.ServiceManager, "control", lambda self, name: calls.append(name) or name)
    assert manager.start() == "start"
    assert manager.stop() == "stop"
    assert manager.restart() == "restart"
    assert calls == ["start", "stop", "restart"]
    assert "restart" in manager.logs("operations")


def test_preflight_persists_real_result_and_classified_log(manager, monkeypatch):
    payload = {"ok": False, "checks": [{"name": "磁盘", "level": "error", "detail": "空间不足"}]}
    monkeypatch.setattr(core.ServiceManager, "server_action", lambda *a: json.dumps(payload))
    assert manager.preflight()["ok"] is False
    stored = json.loads((manager.config.data_root / "config/preflight.status.json").read_text(encoding="utf-8"))
    assert stored["ok"] is False and stored["checked_at"]
    assert "空间不足" in manager.logs("preflight")


@pytest.mark.parametrize("failure", [False, True])
def test_backup_quiesces_web_and_restores_even_on_failure(manager, monkeypatch, failure):
    order = []
    monkeypatch.setattr(core.ServiceManager, "status", lambda self: {"owned": True, "state": "running"})
    monkeypatch.setattr(core.ServiceManager, "control", lambda self, name: order.append(name))
    def backup(self, action):
        order.append(action)
        if failure:
            raise RuntimeError("test backup failed")
        return "备份完成：test-path"
    monkeypatch.setattr(core.ServiceManager, "server_action", backup)
    if failure:
        with pytest.raises(RuntimeError, match="test backup failed"):
            manager.backup()
    else:
        assert "备份完成" in manager.backup()
    assert order == ["stop", "--backup", "start"]


def test_backup_never_controls_foreign_service(manager, monkeypatch):
    monkeypatch.setattr(core.ServiceManager, "status", lambda self: {"owned": False, "state": "running"})
    monkeypatch.setattr(core.ServiceManager, "control", lambda *a: pytest.fail("must not stop foreign service"))
    with pytest.raises(RuntimeError, match="归属"):
        manager.backup()


def test_stopped_service_backup_does_not_start_it(manager, monkeypatch):
    monkeypatch.setattr(core.ServiceManager, "status", lambda self: {"owned": True, "state": "stopped"})
    monkeypatch.setattr(core.ServiceManager, "control", lambda *a: pytest.fail("must retain stopped state"))
    monkeypatch.setattr(core.ServiceManager, "server_action", lambda *a: "备份完成：test")
    manager.backup()


def test_failed_resume_is_explicit_even_after_successful_backup(manager, monkeypatch):
    monkeypatch.setattr(core.ServiceManager, "status", lambda self: {"owned": True, "state": "running"})
    def control(self, name):
        if name == "start":
            raise RuntimeError("cannot resume")
    monkeypatch.setattr(core.ServiceManager, "control", control)
    monkeypatch.setattr(core.ServiceManager, "server_action", lambda *a: "备份完成：test")
    with pytest.raises(RuntimeError, match="Web 未恢复"):
        manager.backup()


def test_partial_backup_is_never_reported_complete(manager):
    folder = manager.config.data_root / "backups/20261107"
    folder.mkdir()
    (folder / "manifest.json").write_text(json.dumps({"complete": True, "database": manager.config.db_name, "storage_included": True, "created_at": "test"}))
    assert not manager.backup_status(manager.config)
    (folder / "database.dump").write_bytes(b"PGDMP")
    (folder / "storage").mkdir()
    assert manager.backup_status(manager.config)["path"] == str(folder)


def test_old_backup_is_visible_but_not_claimed_new_complete_backup(manager):
    folder = manager.config.data_root / "backups/old"
    folder.mkdir()
    (folder / "manifest.json").write_text(json.dumps({"database": manager.config.db_name, "storage_included": True, "created_at": "old"}))
    (folder / "database.dump").write_bytes(b"PGDMP")
    (folder / "storage").mkdir()
    assert manager.backup_status(manager.config)["legacy"] is True


def test_continuation_never_creates_database_or_saves_config(manager, monkeypatch):
    from deployment.installer import deploy
    monkeypatch.setattr(DeploymentConfig, "save", lambda self: pytest.fail("must not save"))
    with pytest.raises(ValueError, match="不能创建新库"):
        deploy(manager.home, manager.config, "continue", "admin", "test-only-password", database_admin={"create_dedicated": True})


def test_status_database_check_is_independent_of_web(manager, monkeypatch):
    monkeypatch.setattr(core, "lan_ipv4", lambda: ["192.168.1.20"])
    monkeypatch.setattr(core.ServiceManager, "status", lambda self: {"owned": True, "state": "stopped"})
    monkeypatch.setattr(core.ServiceManager, "server_action", lambda *a: json.dumps({"connected": True, "revision": "head", "head": "head"}))
    result = manager.status()
    assert result["database"]["connected"] and not result["web"]
    assert result["version"]


def test_autostart_uses_scm_and_never_registers_a_task(manager, monkeypatch):
    calls = []
    monkeypatch.setattr(core.ServiceManager, "status", lambda self: {"owned": True})
    from types import SimpleNamespace
    monkeypatch.setattr(core, "run", lambda *a, **k: None)
    import deployment.service as service
    monkeypatch.setattr(service, "run", lambda args, **kwargs: calls.append(args) or SimpleNamespace(returncode=0))
    assert "开机" in manager.install_autostart()
    assert calls == [["sc.exe", "config", service.SERVICE_ID, "start=", "delayed-auto"]]


def test_bounded_logs_and_only_one_current_gui_entry(manager):
    log = manager.config.data_root / "logs/operations.log"
    log.write_text("\n".join(str(number) for number in range(200)), encoding="utf-8")
    assert len(core.tail(log, 20).splitlines()) == 20
    web = Path(__file__).resolve().parents[2]
    assert not (web / "console_v1.py").exists()
    assert not (web / "server_worker.py").exists()
    assert not (web / "portable_runtime.py").exists()
    assert 'str(WEB / "launcher.py")' in (web / "build_formal_windows.py").read_text(encoding="utf-8")
    source = (web / "launcher.py").read_text(encoding="utf-8")
    close_handler = source.split("    def closeEvent(self, event):", 1)[1].split("\n\ndef main", 1)[0]
    assert "self.manager.stop(" not in close_handler
