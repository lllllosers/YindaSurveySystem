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

    build_web_bundle()
    output = OUTPUT_ROOT / "yinda-web-windows-portable.zip"
    with tempfile.TemporaryDirectory(prefix="yinda-portable-") as temporary:
        root = Path(temporary)
        with ZipFile(OUTPUT_ROOT / "yinda-web-center.zip") as archive:
            archive.extractall(root)

        portable_files = WEB_ROOT / "portable_windows"
        for file in portable_files.iterdir():
            if file.is_file():
                shutil.copy2(file, root / file.name)

        python_root = root / "runtime" / "python"
        python_root.mkdir(parents=True)
        with ZipFile(embed_zip) as archive:
            archive.extractall(python_root)
        path_file = python_root / "python312._pth"
        if not path_file.exists():
            parser.error("需要 Python 3.12 x64 嵌入式运行时。")
        path_file.write_text(
            "python312.zip\n.\nLib\\site-packages\n..\\..\n..\\..\\web_center\\backend\nimport site\n",
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

        guide = root / "先看这里.txt"
        guide.write_text(
            "引大调查 Web 系统 · Windows 验收部署包\n\n"
            "1. 将压缩包完整解压到固定文件夹，例如 C:\\YindaWeb。不要在 ZIP 预览窗口内运行。\n"
            "2. 双击 Start-Yinda.bat。首次启动会初始化数据库并提示创建管理员。\n"
            "3. 浏览器会打开 http://127.0.0.1:8000/；以后开机后再次双击 Start-Yinda.bat。\n"
            "4. 关闭服务请双击 Stop-Yinda.bat；备份请双击 Backup-Yinda.bat。\n\n"
            "账号、业务数据与上传文件仅保存在解压目录内；不要删除 data、"
            "web_center\\backend\\.env 或 web_center\\backend\\storage。\n"
            "这个包完成的是电脑本机启动。给甲方外网网址前，须按 DEPLOY.md 配置 production、"
            "运行 production_check，并配置 HTTPS 公网入口。\n"
            "首次启动如提示缺少 Visual C++ 运行库，可运行 runtime\\vcredist_x64.exe。\n",
            encoding="utf-8-sig",
        )

        forbidden = {".env", ".venv", ".git", "node_modules", "storage", "backups", "tests"}
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
