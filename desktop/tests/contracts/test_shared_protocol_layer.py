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




def test_desktop_adapters_use_the_shared_protocol_implementations() -> None:
    assert desktop_build_business_code is build_business_code
    assert desktop_parse_stake is parse_stake
    assert desktop_task_reader is inspect_survey_task_package
    assert desktop_result_reader is inspect_survey_result_package


def test_shared_identity_and_code_examples_remain_stable() -> None:
    assert desktop_master_uid("organization", "ORG-D01") == deterministic_master_uid(
        "organization", "ORG-D01"
    )
