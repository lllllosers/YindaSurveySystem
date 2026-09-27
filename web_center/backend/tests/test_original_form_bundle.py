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
        assert "src/services/original_form_renderer.py" in names
        assert "src/services/original_form_export_common.py" in names
        assert "web_center/backend/app/services/original_form_export.py" in names
        requirements = archive.read("web_center/backend/requirements.txt").decode("utf-8")
        assert "openpyxl" in requirements
        assert not any(name.endswith("/.env") or "/storage/" in name or "/backups/" in name or "/.runtime/" in name for name in names)
