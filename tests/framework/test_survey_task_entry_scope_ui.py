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
    def test_cached_task_scope_snapshot_filters_canals(
        self,
        mock_departments,
        mock_offices,
        mock_canals,
        mock_codes,
    ):
        mock_departments.return_value = [
            {
                "id": 10,
                "name": "任务基层处",
                "business_code": "1",
                "status": "active",
            },
            {
                "id": 11,
                "name": "任务外基层处",
                "business_code": "2",
                "status": "active",
            },
        ]

        mock_offices.return_value = [
            {
                "id": 20,
                "name": "任务水管所",
                "business_code": "01",
                "status": "active",
            },
            {
                "id": 21,
                "name": "任务外水管所",
                "business_code": "02",
                "status": "active",
            },
        ]

        mock_canals.return_value = [
            {
                "id": 30,
                "name": "任务渠系",
                "canal_level": "03",
            },
            {
                "id": 31,
                "name": "任务外渠系",
                "canal_level": "03",
            },
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
                    "management_scope_uid": (
                        "scope-task-001"
                    ),
                    "canal_unit_id": 30,
                },
            ),
        }

        self.page.load_departments()

        self.assertEqual(
            self.page.department_combo.count(),
            1,
        )
        self.assertEqual(
            self.page.office_combo.count(),
            1,
        )
        self.assertEqual(
            self.page.canal_combo.count(),
            1,
        )
        self.assertEqual(
            self.page.department_combo.currentData()[
                "id"
            ],
            10,
        )
        self.assertEqual(
            self.page.office_combo.currentData()[
                "id"
            ],
            20,
        )
        self.assertEqual(
            self.page.canal_combo.currentData()[
                "id"
            ],
            30,
        )


if __name__ == "__main__":
    unittest.main()
