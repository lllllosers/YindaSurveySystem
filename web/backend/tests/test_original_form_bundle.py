import os
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile


WEB_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WEB_ROOT))
import build_deploy_bundle  # noqa: E402


def test_bundle_contains_templates_and_renderer_without_runtime_data(tmp_path, monkeypatch):
    monkeypatch.setattr(build_deploy_bundle, "OUTPUT_ROOT", tmp_path)
    build_deploy_bundle.main()
    with ZipFile(tmp_path / "yinda-web-center.zip") as archive:
        names = set(archive.namelist())
        assert len([name for name in names if name.startswith("templates/excel/form_2_") and name.endswith("_V1.xlsx")]) == 14
        assert "shared/export/original_form_renderer.py" in names
        assert "shared/export/original_form_export_common.py" in names
        assert not any(name.startswith(("src/", "desktop/")) for name in names)
        assert "web_center/backend/app/services/original_form_export.py" in names
        assert "web_center/server_console_core.py" in names
        assert "web_center/server_worker.py" in names
        assert "web_center/launcher.py" in names
        if (build_deploy_bundle.OUTPUT_ROOT / "YindaWebServerConsole.exe").is_file():
            assert "web_center/YindaWebServerConsole.exe" in names
        requirements = archive.read("web_center/backend/requirements.txt").decode("utf-8")
        assert "openpyxl" in requirements
        assert not any(name.endswith("/.env") or "/storage/" in name or "/backups/" in name or "/.runtime/" in name for name in names)
        unpacked = tmp_path / "unpacked"
        archive.extractall(unpacked)
    env = os.environ.copy()
    env.update(
        APP_ENV="test",
        DB_PASSWORD="test-only-password",
        PYTHONPATH=str(unpacked),
    )
    result = subprocess.run(
        [sys.executable, "-c", "import app.main; from app.services.original_form_export import export_central_original_form; from shared.forms.engineering.registry import get_engineering_form_definitions; print(len(get_engineering_form_definitions()))"],
        cwd=unpacked / "web_center" / "backend",
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "14"
