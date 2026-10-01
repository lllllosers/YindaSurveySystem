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


from PySide6.QtWidgets import (
    QApplication,
)

from pages.components.generic_engineering_survey_page import (
    GenericEngineeringSurveyPage,
)
from tests.framework.engineering_test_fixtures import (
    TEST_POINT_DEFINITION,
)


class CanalManagementScopeEntryUiTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(
        cls,
    ):
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

        self.page.office_combo.blockSignals(
            True
        )
        self.page.office_combo.clear()
        self.page.office_combo.addItem(
            "测试管理单位",
            {
                "id": 20,
                "business_code": "01",
            },
        )
        self.page.office_combo.setCurrentIndex(
            0
        )
        self.page.office_combo.blockSignals(
            False
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
    def test_new_entry_requests_only_active_management_scopes(
        self,
        mock_canals,
        mock_codes,
    ):
        mock_canals.return_value = [
            {
                "id": 30,
                "name": "测试渠系",
                "canal_level": "03",
            }
        ]

        self.page.current_context = {
            "project_id": 1,
            "batch_id": 2,
        }

        self.page.editing_record_id = None

        self.page.office_changed()

        mock_canals.assert_called_once_with(
            20,
            active_only=True,
        )

        self.assertEqual(
            self.page.canal_combo.count(),
            1,
        )

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
    def test_existing_record_can_request_inactive_historical_scope(
        self,
        mock_canals,
        mock_codes,
    ):
        mock_canals.return_value = [
            {
                "id": 30,
                "name": "历史渠系",
                "canal_level": "03",
            }
        ]

        self.page.current_context = {
            "project_id": 1,
            "batch_id": 2,
        }

        self.page.editing_record_id = 999

        self.page.office_changed()

        mock_canals.assert_called_once_with(
            20,
            active_only=False,
        )

        self.assertEqual(
            self.page.canal_combo.count(),
            1,
        )


if __name__ == "__main__":
    unittest.main()
