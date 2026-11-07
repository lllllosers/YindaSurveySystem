"""Product identity and packaged resources shared by the existing GUI and builder."""
from pathlib import Path
import json
import sys

PRODUCT_NAME = "引大调查数据采集系统"
PRODUCT_EXE = "引大调查Web中心.exe"
PACKAGE_NAME = "YindaWebCenter-Windows-x64.zip"


def asset(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / "assets" / name


def product_version():
    info = asset("build-info.json")
    return json.loads(info.read_text(encoding="utf-8"))["version"] if info.is_file() else "Web Center · 开发版本"
