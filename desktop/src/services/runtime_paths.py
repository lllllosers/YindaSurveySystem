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


def get_repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def get_templates_root(application_root: Path) -> Path:
    """Source uses the sole repository templates; installed EXE uses its sibling."""
    desktop_root = Path(__file__).resolve().parents[2]
    if getattr(sys, "frozen", False) or application_root != desktop_root:
        return application_root / "templates"
    return get_repository_root() / "templates"
