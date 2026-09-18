import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from PySide6.QtWidgets import QApplication

from pages.components.generic_engineering_survey_page import (
    GenericEngineeringSurveyPage,
)
from tests.framework.engineering_test_fixtures import (
    TEST_POINT_DEFINITION,
)


class SurveyTaskEntryScopeUiTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def setUp(self):
        self.page = (
            GenericEngineeringSurveyPage(
                TEST_POINT_DEFINITION
            )
        )

    def tearDown(self):
        self.page.deleteLater()

    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_engineering_business_codes",
        return_value=[],
    )
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_managed_canals_for_organization"
    )
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_water_offices"
    )
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_departments"
    )
    def test_task_snapshot_keeps_exact_scope_choice(
        self,
        mock_departments,
        mock_offices,
        mock_live_canals,
        mock_codes,
    ):
        mock_departments.return_value = [
            {
                "id": 10,
                "name": "任务基层处",
                "business_code": "1",
                "status": "active",
            }
        ]
        mock_offices.return_value = [
            {
                "id": 20,
                "name": "任务水管所",
                "business_code": "01",
                "status": "active",
            }
        ]

        self.page.current_context = {
            "project_id": 1,
            "batch_id": 2,
        }
        self.page._entry_task_workspace = {
            "department_id": 10,
            "organization_unit_id": 20,
            "management_scopes": (
                {
                    "management_scope_uid": "scope-a",
                    "canal_unit_id": 30,
                    "canal_name": "总干渠",
                    "canal_level": "01",
                    "range_mode": "segment_unknown",
                    "description": "第一分管段",
                },
                {
                    "management_scope_uid": "scope-b",
                    "canal_unit_id": 30,
                    "canal_name": "总干渠",
                    "canal_level": "01",
                    "range_mode": "segment_known",
                    "start_stake_text": "K10+000",
                    "start_stake_value": 10000.0,
                    "end_stake_text": "K20+000",
                    "end_stake_value": 20000.0,
                    "description": "第二分管段",
                },
                {
                    "management_scope_uid": "scope-c",
                    "canal_unit_id": 31,
                    "canal_name": "通远支渠",
                    "canal_level": "03",
                    "range_mode": "whole",
                    "description": "",
                },
            ),
        }

        self.page.load_departments()

        mock_live_canals.assert_not_called()

        self.assertEqual(
            self.page.canal_combo.count(),
            2,
        )
        self.assertEqual(
            self.page.canal_combo.currentData()[
                "id"
            ],
            30,
        )
        self.assertEqual(
            self.page.task_scope_combo.count(),
            2,
        )
        self.assertIn(
            "边界未知",
            self.page.task_scope_combo.itemText(
                0
            ),
        )
        self.assertIn(
            "K10+000～K20+000",
            self.page.task_scope_combo.itemText(
                1
            ),
        )

        self.page.task_scope_combo.setCurrentIndex(
            1
        )

        ownership = (
            self.page.collect_ownership_data()
        )

        self.assertEqual(
            ownership[
                "management_scope_uid"
            ],
            "scope-b",
        )

        self.page.canal_combo.setCurrentIndex(
            1
        )

        self.assertEqual(
            self.page.task_scope_combo.count(),
            1,
        )
        self.assertEqual(
            self.page.task_scope_combo.currentData()[
                "management_scope_uid"
            ],
            "scope-c",
        )


if __name__ == "__main__":
    unittest.main()
