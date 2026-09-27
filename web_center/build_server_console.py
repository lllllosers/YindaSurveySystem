"""Build the Windows x64 production console without application secrets."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import platform
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def main() -> None:
    if sys.platform != "win32" or platform.architecture()[0] != "64bit":
        raise SystemExit("服务控制台 EXE 仅能在 Windows x64 构建。")
    for module in ("PySide6", "PyInstaller"):
        if importlib.util.find_spec(module) is None:
            raise SystemExit(f"缺少构建依赖 {module}，请安装 web_center/console-requirements.txt。")
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
    except ImportError as exc:
        raise SystemExit("PySide6 Qt DLL 无法加载；请使用独立的 Windows x64 Python 虚拟环境构建。") from exc
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", "--onefile", "--windowed",
            "--noconfirm", "--clean", "--name", "YindaWebServerConsole",
            "--distpath", str(ROOT / "release"),
            "--workpath", str(ROOT / "build" / "server_console"),
            "--specpath", str(ROOT / "build" / "server_console"),
            str(ROOT / "launcher.py"),
        ],
        cwd=ROOT,
        check=True,
    )
    print(f"控制台：{ROOT / 'release' / 'YindaWebServerConsole.exe'}")


if __name__ == "__main__":
    main()
