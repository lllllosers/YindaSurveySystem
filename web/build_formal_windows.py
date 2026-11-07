"""Reproducible onedir delivery; each run owns a fresh build/output directory."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile

from build_server_console import clean_build_environment
from branding import PRODUCT_NAME, PRODUCT_EXE, PACKAGE_NAME

WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
WINSW_SHA256 = "05b82d46ad331cc16bdc00de5c6332c1ef818df8ceefcd49c726553209b3a0da"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--winsw", type=Path, required=True, help="Official WinSW v2.12.0 x64 executable")
    args = parser.parse_args()
    if sys.platform != "win32" or sys.maxsize <= 2**32:
        raise SystemExit("请在 Windows x64 构建。")
    with args.winsw.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != WINSW_SHA256:
            raise SystemExit("WinSW 构建输入校验失败。")
    license_file = args.winsw.parent / "LICENSE.txt"
    if not license_file.is_file():
        raise SystemExit("WinSW 构建输入目录缺少官方 LICENSE.txt。")
    if not (WEB / "frontend" / "dist" / "index.html").is_file():
        raise SystemExit("请先执行 npm ci && npm run build。")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    stage = WEB / "build" / "formal-v1" / stamp
    output = WEB / "release" / "web-center-windows" / stamp
    package = output / "YindaWebCenter"
    stage.mkdir(parents=True, exist_ok=False)
    package.mkdir(parents=True, exist_ok=False)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    version = "Web Center · " + stamp[:8] + " · " + commit[:8]
    gui_assets = stage / "gui-assets"
    shutil.copytree(WEB / "assets", gui_assets)
    (gui_assets / "build-info.json").write_text(json.dumps({"version": version, "source_commit": commit}, ensure_ascii=False), encoding="utf-8")
    env = clean_build_environment()
    env["PYTHONPATH"] = os.pathsep.join(map(str, (WEB / "backend", WEB, ROOT)))
    env.update(DB_PASSWORD="build-smoke-only-secret", APP_ENV="test", YINDA_CONFIG_FILE=str(stage / "nonexistent.env"))
    common = [sys.executable, "-m", "PyInstaller", "--onedir", "--noconfirm", "--noupx",
              "--paths", str(WEB), "--paths", str(WEB / "backend"), "--paths", str(ROOT),
              "--workpath", str(stage / "work"), "--specpath", str(stage), "--distpath", str(stage / "dist")]
    server = common + ["--name", "YindaWebServer", "--console", "--exclude-module", "PySide6",
        "--icon", str(WEB / "assets/YindaWebCenter.ico"),
        "--exclude-module", "alembic.testing", "--exclude-module", "shared.tests", "--exclude-module", "pytest",
        "--collect-submodules", "app", "--collect-submodules", "shared", "--collect-submodules", "uvicorn",
        "--collect-submodules", "alembic",
        "--hidden-import", "sqlalchemy.dialects.postgresql.psycopg", "--collect-all", "psycopg_binary"]
    # Alembic paths match BACKEND_DIR in the frozen app module (_internal).
    server += [
        "--add-data", f"{WEB / 'backend' / 'alembic'}{os.pathsep}alembic",
        "--add-data", f"{WEB / 'backend' / 'alembic.ini'}{os.pathsep}.",
        "--add-data", f"{WEB / 'frontend' / 'dist'}{os.pathsep}frontend",
        "--add-data", f"{ROOT / 'shared' / 'master_data' / 'official_master_contract.json'}{os.pathsep}shared/master_data",
        "--add-data", f"{ROOT / 'templates' / 'excel'}{os.pathsep}templates/excel", str(WEB / "server_entry.py")]
    subprocess.run(server, cwd=WEB, env=env, check=True)
    console_name = PRODUCT_EXE.removesuffix(".exe")
    console = common + ["--name", console_name, "--windowed", "--exclude-module", "app",
                       "--icon", str(WEB / "assets/YindaWebCenter.ico"),
                       "--add-data", f"{gui_assets}{os.pathsep}assets",
                       str(WEB / "launcher.py")]
    subprocess.run(console, cwd=WEB, env=env, check=True)
    service = package / "service"
    service.mkdir()
    shutil.copytree(stage / "dist" / "YindaWebServer", service / "YindaWebServer")
    console_dist = stage / "dist" / console_name
    shutil.copy2(console_dist / PRODUCT_EXE, package / PRODUCT_EXE)
    shutil.copytree(console_dist / "_internal", package / "_internal")
    shutil.copy2(args.winsw, service / "YindaWebService.exe")
    shutil.copy2(license_file, service / "WinSW-LICENSE.txt")
    shutil.copy2(ROOT / "docs" / "web" / "SERVER_CONSOLE_V1.md", package / "部署说明.md")
    for name in ("SERVER_CONSOLE_V1_WINDOWS_ACCEPTANCE.md", "SERVER_CONSOLE_V1_WINDOWS_ACCEPTANCE_RECORD.md", "SERVER_CONSOLE_UNIFICATION.md"):
        shutil.copy2(ROOT / "docs" / "web" / name, package / name)
    manifest = {"product_name": PRODUCT_NAME + " Web Center", "version": version, "source_commit": commit, "layout": 2,
                "gui_entry": "launcher.py", "gui_executable": PRODUCT_EXE, "operations_entry": "server_console_core.py", "winsw": "2.12.0", "winsw_sha256": WINSW_SHA256,
                "files": {}}
    for path in sorted(package.rglob("*")):
        if path.is_file():
            with path.open("rb") as stream:
                manifest["files"][path.relative_to(package).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    (package / "build-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run([str(service / "YindaWebServer" / "YindaWebServer.exe"), "--smoke-test"], env=env, check=True, timeout=60)
    subprocess.run([str(package / PRODUCT_EXE), "--smoke-test"], env=env, check=True, timeout=60)
    archive = output / PACKAGE_NAME
    with ZipFile(archive, "w", ZIP_DEFLATED) as zipped:
        for path in package.rglob("*"):
            if path.is_file():
                zipped.write(path, Path(package.name) / path.relative_to(package))
    print(f"交付目录：{package}\n交付包：{archive}")


if __name__ == "__main__":
    main()
