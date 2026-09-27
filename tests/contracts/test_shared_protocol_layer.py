from __future__ import annotations

import ast
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from services.business_code import build_business_code as desktop_build_business_code
from services.master_identity import deterministic_master_uid as desktop_master_uid
from services.stake import parse_stake as desktop_parse_stake
from services.survey_result_package_reader import (
    inspect_survey_result_package as desktop_result_reader,
)
from services.survey_task_package_reader import (
    inspect_survey_task_package as desktop_task_reader,
)
from shared.protocol.business_code import build_business_code
from shared.protocol.identity import deterministic_master_uid
from shared.protocol.result_package_reader import inspect_survey_result_package
from shared.protocol.revision import classify_revision_values
from shared.protocol.stake import parse_stake
from shared.protocol.task_package_reader import inspect_survey_task_package


def test_shared_protocol_has_no_ui_web_or_database_dependencies() -> None:
    forbidden_roots = {
        "PySide6",
        "app",
        "database",
        "fastapi",
        "forms",
        "services",
        "sqlalchemy",
    }
    violations: list[str] = []
    protocol_root = PROJECT_ROOT / "shared" / "protocol"

    for path in sorted(protocol_root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".", 1)[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = {node.module.split(".", 1)[0]}
            else:
                continue
            blocked = roots & forbidden_roots
            if blocked:
                violations.append(f"{path.name}:{node.lineno}:{','.join(sorted(blocked))}")

    assert violations == []


def test_desktop_adapters_use_the_shared_protocol_implementations() -> None:
    assert desktop_build_business_code is build_business_code
    assert desktop_parse_stake is parse_stake
    assert desktop_task_reader is inspect_survey_task_package
    assert desktop_result_reader is inspect_survey_result_package


def test_shared_identity_and_code_examples_remain_stable() -> None:
    assert desktop_master_uid("organization", "ORG-D01") == deterministic_master_uid(
        "organization", "ORG-D01"
    )
    assert deterministic_master_uid("organization", "ORG-D01") == (
        "d3f2f31e9c37ede995b19ab5a821792e"
    )
    assert build_business_code("1", "01", "03", "02", 1) == "1-01-03-02-001"
    assert parse_stake("K12+350") == ("CH12+350", 12350.0)


def test_shared_revision_contract_covers_idempotency_and_divergence() -> None:
    assert classify_revision_values(
        same_identity=True,
        same_content=True,
        incoming_revision=1,
        local_revision=3,
        source_revision=1,
    )[0] == "existing"
    assert classify_revision_values(
        same_identity=True,
        same_content=False,
        incoming_revision=1,
        local_revision=1,
        source_revision=2,
    )[0] == "stale"
    assert classify_revision_values(
        same_identity=True,
        same_content=False,
        incoming_revision=2,
        local_revision=2,
        source_revision=1,
    )[0] == "diverged"
    assert classify_revision_values(
        same_identity=False,
        same_content=True,
        incoming_revision=2,
        local_revision=1,
        source_revision=1,
    )[0] == "identity_conflict"
