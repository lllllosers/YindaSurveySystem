"""Create a small Web-only deployment archive without desktop UI or local data."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import sys


WEB_ROOT = Path(__file__).resolve().parent
REPO_ROOT = WEB_ROOT.parent
OUTPUT_ROOT = WEB_ROOT / "release"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_python_tree(source: Path, target: Path) -> None:
    for file in source.rglob("*.py"):
        copy_file(file, target / file.relative_to(source))


def main() -> None:
    dist = WEB_ROOT / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        raise SystemExit("请先在 web_center/frontend 运行 npm ci 和 npm run build。")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bundle = OUTPUT_ROOT / f"yinda-web-center-{stamp}"
    bundle.mkdir(parents=True, exist_ok=False)

    copy_python_tree(WEB_ROOT / "backend" / "app", bundle / "web_center" / "backend" / "app")
    copy_python_tree(WEB_ROOT / "backend" / "alembic", bundle / "web_center" / "backend" / "alembic")
    for name in ("alembic.ini", "requirements.txt", ".env.example"):
        copy_file(WEB_ROOT / "backend" / name, bundle / "web_center" / "backend" / name)
    shutil.copytree(dist, bundle / "web_center" / "frontend" / "dist")
    shutil.copytree(REPO_ROOT / "shared", bundle / "shared", ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc", ".env", ".venv", "node_modules", "storage", "backups", ".runtime"))

    from shared.forms.engineering.registry import get_engineering_form_definitions
    for definition in get_engineering_form_definitions():
        filename = definition.original_form_export_definition.template_filename
        template = REPO_ROOT / "templates" / "excel" / filename
        if not template.is_file():
            raise FileNotFoundError("正式原表模板不完整。")
        copy_file(template, bundle / "templates" / "excel" / filename)

    for name in ("launcher.py", "server_console_core.py", "portable_runtime.py", "server_worker.py", "build_server_console.py", "console-requirements.txt"):
        copy_file(WEB_ROOT / name, bundle / "web_center" / name)
    console_exe = OUTPUT_ROOT / "YindaWebServerConsole.exe"
    if console_exe.is_file():
        copy_file(console_exe, bundle / "web_center" / console_exe.name)

    copy_file(WEB_ROOT / "DEPLOY.md", bundle / "DEPLOY.md")
    forbidden_parts = {".env", ".venv", "node_modules", "storage", "backups", ".runtime", ".git", ".pytest_cache"}
    forbidden_suffixes = {".key", ".pem", ".p12", ".token"}
    for file in bundle.rglob("*"):
        if file.is_file() and (forbidden_parts.intersection(file.relative_to(bundle).parts) or file.suffix.lower() in forbidden_suffixes):
            raise RuntimeError(f"部署包包含运行时或敏感文件：{file.relative_to(bundle)}")
    archive = shutil.make_archive(str(OUTPUT_ROOT / "yinda-web-center"), "zip", bundle)
    shutil.rmtree(bundle)
    print(f"部署包：{archive}")


if __name__ == "__main__":
    main()
