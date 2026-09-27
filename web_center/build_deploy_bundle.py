"""Create a small Web-only deployment archive without desktop UI or local data."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil


WEB_ROOT = Path(__file__).resolve().parent
REPO_ROOT = WEB_ROOT.parent
OUTPUT_ROOT = WEB_ROOT / "release"


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
    shutil.copytree(REPO_ROOT / "shared", bundle / "shared", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    form_source = REPO_ROOT / "src" / "forms" / "engineering"
    form_target = bundle / "src" / "forms" / "engineering"
    for name in ("__init__.py", "registry.py", "models.py", "extension_models.py", "formatters.py", "list_definitions.py"):
        copy_file(form_source / name, form_target / name)
    for file in form_source.glob("form_2_*.py"):
        copy_file(file, form_target / file.name)
    copy_file(REPO_ROOT / "src" / "forms" / "__init__.py", bundle / "src" / "forms" / "__init__.py")
    copy_file(REPO_ROOT / "src" / "services" / "__init__.py", bundle / "src" / "services" / "__init__.py")
    for file in (REPO_ROOT / "src" / "services").glob("*_evaluation.py"):
        copy_file(file, bundle / "src" / "services" / file.name)
    for name in ("original_form_export_common.py", "original_form_renderer.py"):
        copy_file(REPO_ROOT / "src" / "services" / name, bundle / "src" / "services" / name)
    for definition in form_source.glob("form_2_*.py"):
        template = REPO_ROOT / "templates" / "excel" / f"{definition.stem}_V1.xlsx"
        if not template.is_file():
            raise FileNotFoundError("正式原表模板不完整。")
        copy_file(template, bundle / "templates" / "excel" / template.name)

    copy_file(WEB_ROOT / "DEPLOY.md", bundle / "DEPLOY.md")
    archive = shutil.make_archive(str(OUTPUT_ROOT / "yinda-web-center"), "zip", bundle)
    shutil.rmtree(bundle)
    print(f"部署包：{archive}")


if __name__ == "__main__":
    main()
