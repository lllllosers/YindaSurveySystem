from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


WEB_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WEB_ROOT))
import server_console_core as core  # noqa: E402


@pytest.fixture
def paths(tmp_path):
    root = tmp_path / "web_center"
    backend = root / "backend"
    scripts = backend / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").touch()
    (scripts / "pythonw.exe").touch()
    (backend / ".env").write_text("APP_ENV=production\nPUBLIC_BASE_URL=https://example.com\n", encoding="utf-8")
    (root / "frontend" / "dist").mkdir(parents=True)
    (root / "frontend" / "dist" / "index.html").touch()
    (root / "server_worker.py").touch()
    return core.ConsolePaths.resolve(root)


def _owned(manager, pid=3123):
    manager.pid_file.parent.mkdir(parents=True, exist_ok=True)
    manager.pid_file.write_text(json.dumps({"pid": pid, "worker": str(manager.paths.worker), "executable": str(manager.paths.pythonw), "birth_token": 987654}), encoding="utf-8")


def test_path_resolution_and_public_configuration(paths, monkeypatch):
    assert paths.backend == paths.web_root / "backend"
    assert paths.frontend_dist == paths.web_root / "frontend" / "dist"
    assert core.read_env_value(paths.backend / ".env", "PUBLIC_BASE_URL") == "https://example.com"
    assert core.public_health("") == "未配置公网访问地址"
    monkeypatch.setattr(core, "health_ok", lambda url, timeout=3: url == "https://example.com")
    assert core.public_health("https://example.com") == "正常"
    assert core.public_health("http://example.com") != "正常"


def test_frozen_console_uses_source_layout_from_release(paths, monkeypatch):
    release = paths.web_root / "release"
    release.mkdir()
    monkeypatch.setattr(core.sys, "frozen", True, raising=False)
    monkeypatch.setattr(core.sys, "executable", str(release / "YindaWebServerConsole.exe"))
    assert core.ConsolePaths.resolve().web_root == paths.web_root


def test_venv_redirector_allows_actual_base_pythonw(paths, tmp_path):
    base = tmp_path / "base-python"
    base.mkdir()
    (base / "pythonw.exe").touch()
    (paths.pythonw.parent.parent / "pyvenv.cfg").write_text(f"home = {base}\n", encoding="utf-8")
    manager = core.ServerManager(paths, inspector=lambda pid: (str(base / "pythonw.exe"), 987654))
    _owned(manager)
    manager.pid_file.write_text(json.dumps({"pid": 3123, "worker": str(paths.worker), "executable": str(base / "pythonw.exe"), "birth_token": 987654}), encoding="utf-8")
    assert manager.owned_pid() == 3123


def test_health_check_requires_status_ok(monkeypatch):
    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, limit):
            return b'{"status":"ok"}'
    monkeypatch.setattr(core, "urlopen", lambda *args, **kwargs: Response())
    assert core.health_ok("http://127.0.0.1:8000")
    class Unhealthy(Response):
        def read(self, limit):
            return b'{"status":"error"}'
    monkeypatch.setattr(core, "urlopen", lambda *args, **kwargs: Unhealthy())
    assert not core.health_ok("http://127.0.0.1:8000")


def test_preflight_blocker_prevents_spawn(paths, monkeypatch):
    launches = []
    manager = core.ServerManager(paths, popen=lambda *args, **kwargs: launches.append(args))
    monkeypatch.setattr(core, "port_open", lambda port: False)
    monkeypatch.setattr(manager, "preflight", lambda: (False, "BLOCKER: 配置不安全"))
    with pytest.raises(RuntimeError, match="预检未通过"):
        manager.start()
    assert launches == []


def test_owned_service_is_not_started_twice(paths, monkeypatch):
    manager = core.ServerManager(paths, inspector=lambda pid: (str(paths.pythonw), 987654))
    _owned(manager)
    monkeypatch.setattr(manager, "preflight", lambda: pytest.fail("不应再次预检"))
    assert "不会重复" in manager.start()


def test_reused_pid_is_not_treated_as_owned(paths):
    manager = core.ServerManager(paths, inspector=lambda pid: (str(paths.pythonw), 123456))
    _owned(manager)
    assert manager.owned_pid() is None


def test_foreign_port_is_never_killed(paths, monkeypatch):
    calls = []
    manager = core.ServerManager(paths, inspector=lambda pid: ("C:/other.exe", 987654), runner=lambda *a, **k: calls.append(a))
    _owned(manager)
    monkeypatch.setattr(core, "port_open", lambda port: True)
    with pytest.raises(RuntimeError, match="非本控制台"):
        manager.start()
    with pytest.raises(RuntimeError, match="非本控制台"):
        manager.stop()
    assert calls == []


def test_start_stop_restart_state_machine(paths, monkeypatch):
    state = {"pid": None, "launches": 0, "kills": 0}
    def inspector(pid):
        return (str(paths.pythonw), 987654) if state["pid"] == pid else None
    def popen(*args, **kwargs):
        state["launches"] += 1
        state["pid"] = 4000 + state["launches"]
        _owned(manager, state["pid"])
        return SimpleNamespace(pid=state["pid"], poll=lambda: None)
    def terminate(pid):
        state["kills"] += 1
        state["pid"] = None
        return True
    manager = core.ServerManager(paths, inspector=inspector, popen=popen, terminator=terminate)
    monkeypatch.setattr(manager, "preflight", lambda: (True, "PASS"))
    monkeypatch.setattr(core, "port_open", lambda port: False)
    monkeypatch.setattr(core, "health_ok", lambda *args, **kwargs: True)
    assert "已启动" in manager.start()
    assert state["launches"] == 1
    assert "不会重复" in manager.start()
    assert "已停止" in manager.stop()
    assert state["kills"] == 1
    assert "已启动" in manager.restart()
    assert state["launches"] == 2


def test_preflight_and_backup_invoke_existing_cli(paths):
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        if "production_check" in command:
            return subprocess.CompletedProcess(command, 0, "PASS: production ready\n", "")
        return subprocess.CompletedProcess(command, 0, "备份完成：D:\\backup\\2026\n", "")
    manager = core.ServerManager(paths, runner=runner)
    assert manager.preflight()[0]
    assert manager.backup().startswith("备份完成：")
    assert [command[-1] for command in calls] == ["app.cli.production_check", "app.cli.backup_web_center"]


def test_autostart_registers_windows_task_without_overwriting_foreign_one(paths):
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        if command[0] == "schtasks.exe":
            return subprocess.CompletedProcess(command, 1, "", "not found")
        return subprocess.CompletedProcess(command, 0, "", "")
    manager = core.ServerManager(paths, runner=runner)
    assert "开机自动启动" in manager.install_autostart()
    assert "New-ScheduledTaskTrigger -AtStartup" in calls[1][-1]
    assert "-UserId 'SYSTEM'" in calls[1][-1]

    foreign = '<Task><Actions><Exec><Command>C:\\other.exe</Command><Arguments>other.py</Arguments></Exec></Actions></Task>'
    conflict = core.ServerManager(paths, runner=lambda command, **kwargs: subprocess.CompletedProcess(command, 0, foreign, ""))
    with pytest.raises(RuntimeError, match="其他程序"):
        conflict.install_autostart()

    owned_task = f'<Task><Actions><Exec><Command>{paths.pythonw}</Command><Arguments>"{paths.worker}"</Arguments></Exec></Actions></Task>'
    update_calls = []
    def update_runner(command, **kwargs):
        update_calls.append(command)
        return subprocess.CompletedProcess(command, 0, owned_task if command[0] == "schtasks.exe" else "", "")
    core.ServerManager(paths, runner=update_runner).install_autostart()
    assert "Set-ScheduledTask" in update_calls[1][-1]


def test_logs_are_bounded_and_gui_close_has_no_stop(paths):
    log = paths.runtime / "logs" / "server.log"
    log.parent.mkdir(parents=True)
    log.write_text("\n".join(str(number) for number in range(200)), encoding="utf-8")
    assert len(core.tail(log, lines=20).splitlines()) == 20
    source = (WEB_ROOT / "launcher.py").read_text(encoding="utf-8")
    close_handler = source.split("    def closeEvent(self, event):", 1)[1].split("\n\ndef main", 1)[0]
    assert ".stop(" not in close_handler
