"""Build the Windows x64 production console without application secrets."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import platform
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def clean_build_environment() -> dict[str, str]:
    """Keep unrelated Qt/ICU DLLs on the developer's PATH out of the bundle."""
    env = os.environ.copy()
    windows = Path(env.get("SystemRoot", r"C:\Windows"))
    search_dirs = (
        Path(sys.executable).parent,
        Path(sys.base_prefix),
        windows / "System32",
        windows,
        windows / "System32" / "Wbem",
    )
    env["PATH"] = os.pathsep.join(str(path) for path in search_dirs if path.is_dir())
    for name in ("PYTHONPATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        env.pop(name, None)
    return env


def main() -> None:
    if sys.platform != "win32" or platform.architecture()[0] != "64bit":
        raise SystemExit("服务控制台 EXE 仅能在 Windows x64 构建。")
    for module in ("PySide6", "PyInstaller"):
        if importlib.util.find_spec(module) is None:
            raise SystemExit(f"缺少构建依赖 {module}，请安装 web/console-requirements.txt。")
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
    except ImportError as exc:
        raise SystemExit("PySide6 Qt DLL 无法加载；请使用独立的 Windows x64 Python 虚拟环境构建。") from exc
    build_env = clean_build_environment()
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
        env=build_env,
    )
    executable = ROOT / "release" / "YindaWebServerConsole.exe"
    subprocess.run([str(executable), "--smoke-test"], cwd=ROOT, check=True, timeout=45, env=build_env)
    print(f"控制台（启动验证通过）：{executable}")


if __name__ == "__main__":
    main()
