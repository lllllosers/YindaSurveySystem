from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from deployment.config import DeploymentConfig, safe_error
from deployment.database import check_adoption
from deployment.service import ServiceManager, event_name, port_available
from deployment import service
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def config(tmp_path):
    return DeploymentConfig(install_root=tmp_path / "引大 程序", data_root=tmp_path / "引大 数据",
        db_password="test-${NO_EXPAND}-pass'\\\"word", allowed_hosts="127.0.0.1,localhost,192.168.1.20")


def test_config_roundtrip_absolute_paths_and_secret(config, monkeypatch, tmp_path):
    config.save()
    monkeypatch.chdir(tmp_path.parent)
    loaded = DeploymentConfig.load(config.install_root)
    assert loaded == config
    assert config.db_password not in repr(loaded)
    assert config.db_password not in (config.install_root / "config/deployment.json").read_text()


@pytest.mark.parametrize("update", [dict(data_root=Path("relative")), dict(data_root=Path("E:/")),
    dict(web_port=0), dict(allowed_hosts="*"), dict(listen_host="8.8.8.8"), dict(db_password="short")])
def test_config_rejects_invalid_values(config, update):
    with pytest.raises(ValueError):
        replace(config, **update).validate()


def test_no_persistent_directory_inside_release(config):
    with pytest.raises(ValueError):
        replace(config, data_root=config.install_root / "service" / "data").validate()


def test_all_business_paths_share_one_base(config):
    settings = Settings(_env_file=None, db_password="test-password", data_root=config.data_root)
    assert settings.storage_dir == config.data_root / "data/storage"
    assert settings.backups_dir == config.data_root / "backups"
    assert settings.file_base / "storage/tasks/x.ydtask" == settings.storage_dir / "tasks/x.ydtask"


def production(**kwargs):
    return Settings(_env_file=None, db_password="test-only-password", app_env="production",
        allowed_hosts="testserver,127.0.0.1", **kwargs)


def test_lan_http_keeps_production_guards():
    settings = production(transport_mode="lan_http", session_cookie_secure=False)
    assert settings.effective_registration_mode == "invite_only"
    app = create_app(settings)
    assert app.docs_url is None and app.openapi_url is None
    client = TestClient(app)
    assert client.get("/api/v1/projects").status_code == 401
    assert client.get("/docs").status_code == 404
    assert client.get("/api/v1/health", headers={"host": "unknown.example"}).status_code == 400
    assert "access-control-allow-origin" not in client.get("/api/v1/health", headers={"origin": "http://localhost:8848"}).headers


@pytest.mark.parametrize("kwargs", [{}, {"transport_mode": "lan_http", "session_cookie_secure": True},
    {"transport_mode": "lan_http", "enable_hsts": True}])
def test_http_requires_explicit_transport_and_valid_cookie_pair(kwargs):
    with pytest.raises(ValidationError):
        production(**kwargs)


def test_new_deployment_cannot_overwrite_any_table_or_file(config):
    with pytest.raises(RuntimeError, match="已有"):
        check_adoption(config, "new", {"tables": {"users"}, "revision": None})
    config.ensure_directories()
    sentinel = config.data_root / "data/storage/keep.bin"
    sentinel.write_bytes(b"retained")
    with pytest.raises(RuntimeError, match="已有"):
        check_adoption(config, "new", {"tables": set(), "revision": None})
    assert sentinel.read_bytes() == b"retained"


def test_continue_requires_identity_and_storage(config):
    with pytest.raises(RuntimeError, match="标识"):
        check_adoption(config, "continue", {"tables": set(), "revision": None})
    config.save()
    config.state_file.write_text(json.dumps({"database": ["elsewhere", 5432, "wrong"]}))
    with pytest.raises(RuntimeError, match="不匹配"):
        check_adoption(config, "continue", {"tables": set(), "revision": None})
    config.state_file.write_text(json.dumps({"database": [config.db_host, config.db_port, config.db_name],
        "data_root": str(config.data_root.resolve()), "phase": "initializing"}))
    with pytest.raises(RuntimeError, match="丢失"):
        check_adoption(config, "continue", {"tables": set(), "revision": None})


def test_service_xml_low_privilege_and_graceful_stop(config):
    manager = ServiceManager(config)
    manager.write_xml()
    xml = ET.parse(manager.wrapper.with_suffix(".xml")).getroot()
    assert xml.findtext("id") == service.SERVICE_ID == "YindaWebCenterService"
    assert xml.findtext("name") == "Yinda Web Center"
    assert xml.findtext("serviceaccount/user") == "LocalService"
    assert xml.findtext("startmode") == "Automatic"
    assert "--stop" in xml.findtext("stoparguments")
    assert config.db_password not in manager.wrapper.with_suffix(".xml").read_text(encoding="utf-8")
    assert xml.findall("onfailure")[-1].get("action") == "none"


def test_foreign_service_never_controlled(config, monkeypatch):
    manager = ServiceManager(config)
    monkeypatch.setattr(manager, "status", lambda: {"state": "running", "owned": False})
    monkeypatch.setattr(service, "run", lambda *a, **k: pytest.fail("must not execute"))
    with pytest.raises(RuntimeError, match="不属于"):
        manager.control("stop")


def test_repeated_start_and_busy_port(config, monkeypatch):
    manager = ServiceManager(config)
    monkeypatch.setattr(manager, "status", lambda: {"state": "running", "owned": True})
    assert "不会重复" in manager.control("start")
    monkeypatch.setattr(manager, "status", lambda: {"state": "stopped", "owned": True})
    monkeypatch.setattr(manager, "legacy_task", lambda: False)
    monkeypatch.setattr(manager, "server_action", lambda action: "ok")
    monkeypatch.setattr(service, "port_available", lambda *a: False)
    with pytest.raises(RuntimeError, match="端口"):
        manager.control("start")


def test_legacy_task_blocks_start(config, monkeypatch):
    manager = ServiceManager(config)
    monkeypatch.setattr(manager, "status", lambda: {"state": "stopped", "owned": True})
    monkeypatch.setattr(manager, "legacy_task", lambda: True)
    with pytest.raises(RuntimeError, match="旧版"):
        manager.control("start")


def test_real_port_occupancy_never_terminates_owner():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        assert not port_available("127.0.0.1", server.getsockname()[1])
        assert server.fileno() >= 0


def test_event_names_are_install_specific(config):
    assert event_name(config, "stop").startswith(r"Global\YindaWebCenterService-stop-")
    assert event_name(config, "stop") != event_name(replace(config, data_root=config.data_root / "other"), "stop")


@pytest.mark.parametrize("enabled", ["true", "false"])
def test_legacy_task_is_blocking_even_when_disabled(config, monkeypatch, enabled):
    calls = []
    def query(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=f"<Task><Settings><Enabled>{enabled}</Enabled></Settings></Task>", stderr="")
    monkeypatch.setattr(service, "run", query)
    assert ServiceManager(config).legacy_task()
    assert calls == [["schtasks.exe", "/Query", "/TN", "YindaWebCenter", "/XML"]]


@pytest.mark.parametrize("message", ["The system cannot find the path specified.", "系统找不到指定的文件。"])
def test_absent_legacy_task_is_not_blocking(config, monkeypatch, message):
    monkeypatch.setattr(service, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr=message))
    assert not ServiceManager(config).legacy_task()


def test_legacy_task_query_denied_does_not_proceed(config, monkeypatch):
    monkeypatch.setattr(service, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="Access is denied."))
    with pytest.raises(RuntimeError, match="无法确认"):
        ServiceManager(config).legacy_task()


@pytest.mark.parametrize("operation", ["deploy", "install", "start", "restart"])
def test_legacy_task_notice_is_consistent_without_mutations(config, monkeypatch, operation):
    from deployment import installer
    if sys.platform != "win32":
        pytest.skip("Windows administrator check")
    monkeypatch.setattr(service.ctypes.windll.shell32, "IsUserAnAdmin", lambda: True)
    monkeypatch.setattr(ServiceManager, "status", lambda self: {"state": "absent" if operation in {"install", "deploy"} else "stopped", "owned": True})
    monkeypatch.setattr(ServiceManager, "legacy_task", lambda self: True)
    monkeypatch.setattr(service, "run", lambda *a, **k: pytest.fail("must not mutate service/task"))
    monkeypatch.setattr(installer, "install_payload", lambda *a: pytest.fail("must not copy payload"))
    monkeypatch.setattr(config, "save", lambda: pytest.fail("must not save configuration"))
    with pytest.raises(RuntimeError) as error:
        if operation == "deploy":
            installer.deploy(config.install_root, config, "new", "admin", "test-only-password")
        elif operation == "install":
            ServiceManager(config).install()
        else:
            ServiceManager(config).control(operation)
    assert str(error.value) == service.LEGACY_TASK_NOTICE
    for text in ("已禁用", "已停止", "导出", "移除", "不会自动删除"):
        assert text in str(error.value)


def test_database_errors_do_not_expose_credentials():
    from sqlalchemy.exc import OperationalError
    assert "password-secret" not in safe_error(OperationalError("dsn password-secret", {}, Exception("password-secret")))


def test_real_legacy_task_detection_and_service_status(config):
    if sys.platform != "win32":
        pytest.skip("Windows-only SCM and Task Scheduler")
    manager = ServiceManager(config)
    status = manager.status()
    assert status["state"] in {"absent", "stopped", "starting", "running", "stopping", "unknown"}
    # Read-only: the probe does not modify any existing service/task.
    assert isinstance(manager.legacy_task(), bool)


def test_online_legacy_relative_path_reads_from_relocated_storage(config, monkeypatch):
    from app.services import online_entry_service as media
    base = config.data_root / "data"
    root = base / "storage/online_media"
    file = root / "entry/media/image.jpg"
    file.parent.mkdir(parents=True)
    file.write_bytes(b"existing-photo")
    monkeypatch.setattr(media, "BACKEND_ROOT", base)
    monkeypatch.setattr(media, "ONLINE_MEDIA_ROOT", root)
    assert media.online_media_path({"storage_relative_path": "storage/online_media/entry/media/image.jpg"}) == file.resolve()
    with pytest.raises(RuntimeError, match="越界"):
        media.online_media_path({"storage_relative_path": "storage/online_media/../../../outside.jpg"})
