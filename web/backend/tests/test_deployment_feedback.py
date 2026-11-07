"""Regression for a deployment silently dropped behind a periodic status refresh."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PySide6.QtWidgets import QApplication, QDialog
import launcher
from launcher import ServerConsole


def test_accepted_wizard_submits_deployment_and_shows_result(tmp_path, monkeypatch):
    """Exercise setup() itself, including the acceptance enum and task handoff."""
    app = QApplication.instance() or QApplication([])
    called = threading.Event()
    class Manager:
        home = tmp_path
        def status(self): return {"config": None, "addresses": [], "checked_at": "test"}
        def deploy(self, *args, progress):
            progress("environment", "running", "test")
            called.set()
            return {"local_url": "http://127.0.0.1:8000", "message": "Web Center 已成功启动"}
    class Wizard:
        config, deploy_mode, username, password, database_admin = None, "new", "admin", "Pass1234", None
        def __init__(self, *args): pass
        def exec(self): return QDialog.DialogCode.Accepted
        def clear_secrets(self): pass
    monkeypatch.setattr(launcher, "SetupWizard", Wizard)
    window = ServerConsole(Manager())
    try:
        deadline = time.monotonic() + 3
        while window.busy and time.monotonic() < deadline:
            app.processEvents()
        window.setup()
        while (not called.is_set() or window.deploying) and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert called.is_set()
        assert window.deployment_dialog.heading.text() == "Web Center 已成功启动"
        assert window.deployment_dialog.return_button.isEnabled()
        assert window.deployment_dialog.url == "http://127.0.0.1:8000"
    finally:
        window.pool.shutdown(wait=True)
        window.timer.stop()
        window.busy = False
        window.exiting = True
        window.close()
        app.processEvents()


def test_deployment_is_not_dropped_when_status_refresh_is_running(tmp_path):
    app = QApplication.instance() or QApplication([])
    release = threading.Event()
    called = threading.Event()
    class Manager:
        home = tmp_path
        def status(self):
            release.wait(4)
            return {"config": None, "addresses": [], "checked_at": "test"}
    window = ServerConsole(Manager())
    try:
        assert window.busy
        window.submit("deploy", lambda: called.set() or "deployment completed")
        release.set()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not called.is_set():
            app.processEvents()
            time.sleep(0.01)
        assert called.is_set(), "deployment was silently dropped by the shared busy flag"
    finally:
        release.set()
        window.pool.shutdown(wait=True)
        window.timer.stop()
        window.busy = False
        window.exiting = True
        window.close()
        app.processEvents()
