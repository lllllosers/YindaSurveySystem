"""Locate the installed PostgreSQL client without requiring a developer PATH."""
import os
from pathlib import Path
import shutil
import re


def installed_bin() -> str:
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\PostgreSQL\Installations") as root:
                for index in range(winreg.QueryInfoKey(root)[0]):
                    with winreg.OpenKey(root, winreg.EnumKey(root, index)) as key:
                        base = Path(winreg.QueryValueEx(key, "Base Directory")[0]) / "bin"
                        version = str(winreg.QueryValueEx(key, "Version")[0])
                        if version.startswith("17") and (base / "pg_dump.exe").is_file():
                            return str(base)
        except OSError:
            pass
    found = shutil.which("pg_dump")
    return str(Path(found).parent) if found else ""


def dump_executable(configured: str = "") -> Path:
    folder = configured or installed_bin()
    result = Path(folder) / ("pg_dump.exe" if os.name == "nt" else "pg_dump")
    if not folder or not result.is_file():
        raise RuntimeError("未找到 PostgreSQL 备份工具，请在运行配置中选择 PostgreSQL 17 的 bin 文件夹。")
    from deployment.service import run
    version = run([result, "--version"], timeout=10)
    if version.returncode or not re.search(r"\b17\.", version.stdout):
        raise RuntimeError("备份工具需使用 PostgreSQL 17 的 pg_dump，请重新选择工具文件夹。")
    return result.resolve()
