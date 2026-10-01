"""Launch console-subsystem tools without a Windows console window."""

from __future__ import annotations

import os
import subprocess
from typing import Any, Callable


def hidden_options() -> dict[str, Any]:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


def hidden_run(args: list[str], *, runner: Callable[..., Any] | None = None, **kwargs: Any) -> Any:
    return (runner or subprocess.run)(args, **hidden_options(), **kwargs)


def hidden_popen(args: list[str], *, popen: Callable[..., Any] | None = None, **kwargs: Any) -> Any:
    return (popen or subprocess.Popen)(args, **hidden_options(), **kwargs)
