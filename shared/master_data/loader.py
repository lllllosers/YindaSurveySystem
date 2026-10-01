import json
from pathlib import Path


def load_official_master_contract(path: Path | None = None) -> dict:
    """Return a fresh copy of the shipped contract; no persistence side effects."""
    source = path or Path(__file__).with_name("official_master_contract.json")
    return json.loads(source.read_text(encoding="utf-8"))
