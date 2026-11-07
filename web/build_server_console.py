"""Compatibility build command and environment helper for the single formal bundle."""

from __future__ import annotations

import os
from pathlib import Path
import sys


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
    # Compatibility command, not a second builder or a standalone old GUI.
    from build_formal_windows import main as build
    build()


if __name__ == "__main__":
    main()
