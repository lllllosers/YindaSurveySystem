from pathlib import Path
import sys
from unittest.mock import patch

import database
from services.runtime_paths import get_templates_root


def test_frozen_database_and_templates_remain_beside_executable(tmp_path):
    executable = tmp_path / "YindaSurveySystem.exe"
    with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(executable)):
        assert database.get_app_root() == tmp_path
        assert database.get_app_root() / "local_data/yinda_survey.db" == tmp_path / "local_data/yinda_survey.db"
        assert get_templates_root(database.get_app_root()) == tmp_path / "templates"


def test_source_templates_have_one_repository_location():
    repository = Path(__file__).resolve().parents[2]
    assert get_templates_root(database.get_app_root()) == repository / "templates"
    assert not (repository / "desktop/templates").exists()
