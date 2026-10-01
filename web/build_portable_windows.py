"""Build a Windows acceptance bundle with app-local Python and PostgreSQL 17."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from build_deploy_bundle import OUTPUT_ROOT, WEB_ROOT, main as build_web_bundle


def copy_runtime(source: Path, target: Path, *, python_packages: bool = False) -> None:
    excluded = ["__pycache__", "*.pyc", "*.pyo"]
    if python_packages:
        excluded += ["tests", "test", "_pytest", "pytest", "pytest-*.dist-info", "iniconfig*", "pluggy*"]
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(*excluded),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-embed", type=Path, required=True)
    parser.add_argument("--site-packages", type=Path, required=True)
    parser.add_argument("--postgres-home", type=Path, required=True)
    args = parser.parse_args()

    embed_zip = args.python_embed.resolve()
    site_packages = args.site_packages.resolve()
    postgres_home = args.postgres_home.resolve()
    for path in (embed_zip, site_packages, postgres_home / "bin" / "initdb.exe"):
        if not path.exists():
            parser.error(f"缺少运行时文件：{path}")
    if not (OUTPUT_ROOT / "YindaWebServerConsole.exe").is_file():
        parser.error("缺少服务控制台 EXE，请先运行 build_server_console.py。")
    for package in ("fastapi", "uvicorn", "sqlalchemy", "alembic", "psycopg", "openpyxl"):
        if not (site_packages / package).is_dir():
            parser.error(f"后端运行环境缺少 {package}，请先安装 requirements.txt。")

    build_web_bundle()
    output = OUTPUT_ROOT / "yinda-web-windows-portable.zip"
    with tempfile.TemporaryDirectory(prefix="yinda-portable-") as temporary:
        root = Path(temporary)
        with ZipFile(OUTPUT_ROOT / "yinda-web-center.zip") as archive:
            archive.extractall(root)

        shutil.copy2(WEB_ROOT.parent / "docs" / "web" / "便携包部署教程.md", root / "便携包部署教程.md")

        python_root = root / "runtime" / "python"
        python_root.mkdir(parents=True)
        with ZipFile(embed_zip) as archive:
            archive.extractall(python_root)
        path_file = python_root / "python312._pth"
        if not path_file.exists():
            parser.error("需要 Python 3.12 x64 嵌入式运行时。")
        path_file.write_text(
            "python312.zip\n.\nLib\\site-packages\n..\\..\n..\\..\\web_center\n..\\..\\web_center\\backend\nimport site\n",
            encoding="utf-8",
        )
        copy_runtime(site_packages, python_root / "Lib" / "site-packages", python_packages=True)

        pg_root = root / "runtime" / "postgres"
        for name in ("bin", "lib", "share"):
            copy_runtime(postgres_home / name, pg_root / name)
        for file in postgres_home.glob("*license*.txt"):
            shutil.copy2(file, pg_root / file.name)
        for file in postgres_home.glob("*LICENSE*.txt"):
            shutil.copy2(file, pg_root / file.name)
        vc_redist = postgres_home / "installer" / "vcredist_x64.exe"
        if vc_redist.exists():
            shutil.copy2(vc_redist, root / "runtime" / "vcredist_x64.exe")

        (root / "先看这里.txt").write_text(
            "引大调查 Web 中心 Windows 便携包\n\n"
            "1. 将 ZIP 完整解压到固定目录，例如 C:\\YindaWeb；不要在压缩包内直接运行。\n"
            "2. 双击 web_center\\YindaWebServerConsole.exe。\n"
            "3. 首次点击“初始化便携环境”，设置管理员，再点击“启动 Web 服务”。\n"
            "4. 点击“打开管理端”进入本机网页；关闭前点击“停止全部”。\n\n"
            "详细步骤、升级与数据备份请阅读同目录的《便携包部署教程.md》。\n",
            encoding="utf-8-sig",
        )

        forbidden = {".env", ".venv", ".git", "node_modules", "storage", "backups", "tests", ".runtime"}
        for file in root.rglob("*"):
            if forbidden.intersection(file.relative_to(root).parts):
                raise RuntimeError(f"部署包包含禁止内容：{file.relative_to(root)}")

        with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            for file in root.rglob("*"):
                if file.is_file():
                    archive.write(file, file.relative_to(root))
    print(f"Windows 验收包：{output}")


if __name__ == "__main__":
    main()
