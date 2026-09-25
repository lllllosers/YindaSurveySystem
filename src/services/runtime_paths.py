from __future__ import annotations

import sys
from pathlib import Path


def get_application_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parents[2]


def get_resource_path(*parts: str) -> Path:
    return get_application_root().joinpath(*parts)
