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

        # 同一物理渠道存在多个 task scope 时，
        # 页面不得默认把第一个 scope 当成用户选择。
        self.assertEqual(
            self.page.task_scope_combo.currentIndex(),
            -1,
        )
        self.assertIsNone(
            self.page.task_scope_combo.currentData()
        )

        with self.assertRaisesRegex(
            ValueError,
            "请选择任务分管范围",
        ):
            self.page.collect_ownership_data()

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
            self.page.task_scope_combo.currentIndex(),
            0,
        )
        self.assertEqual(
            self.page.task_scope_combo.currentData()[
                "management_scope_uid"
            ],
            "scope-c",
        )

    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_task_workspace_scope_snapshot"
    )
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_canal_unit"
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
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_current_form_version"
    )
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_current_context"
    )
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "load_engineering_record_bundle"
    )
    def test_historical_task_record_load_does_not_require_live_scope(
        self,
        mock_bundle,
        mock_context,
        mock_form_version,
        mock_departments,
        mock_offices,
        mock_live_canals,
        mock_canal_unit,
        mock_scope_snapshot,
    ):
        mock_context.return_value = {
            "project_id": 1,
            "batch_id": 2,
        }

        mock_form_version.return_value = {
            "id": 3,
        }

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

        # 当前 live CanalManagementScope 已不存在。
        mock_live_canals.return_value = []

        # 物理 CanalUnit 仍是既有记录的固定身份。
        mock_canal_unit.return_value = {
            "id": 30,
            "name": "总干渠",
            "canal_level": "01",
            "status": "active",
        }

        # 任务下发时冻结的 scope 快照仍用于 provenance 展示。
        mock_scope_snapshot.return_value = {
            "management_scope_uid": (
                "scope-history"
            ),
            "canal_unit_id": 30,
            "canal_unit_uid": (
                "canal-history"
            ),
            "organization_unit_uid": (
                "office-history"
            ),
            "canal_name": "总干渠",
            "canal_level": "01",
            "range_mode": (
                "segment_unknown"
            ),
            "start_stake_text": None,
            "start_stake_value": None,
            "end_stake_text": None,
            "end_stake_value": None,
            "sort_order": 1,
            "status": "active",
            "description": (
                "下发时冻结分管段"
            ),
        }

        mock_bundle.return_value = {
            "record": {
                "survey_record_id": 501,
                "record_status": "draft",
                "source_task_uid": (
                    "task-history"
                ),
                "source_management_scope_uid": (
                    "scope-history"
                ),
                "business_code": (
                    "1010101001"
                ),
                "asset_name": (
                    "历史任务工程"
                ),
                "single_stake_text": (
                    "K10+000"
                ),
                "single_stake_value": (
                    10000.0
                ),
                "department_id": 10,
                "office_id": 20,
                "canal_id": 30,
                "record_data": {
                    "design_flow": 6.5,
                },
                "survey_date": (
                    "2026-09-18"
                ),
                "overall_grade": None,
                "survey_comment": "",
            },
            "inspection_results": [],
        }

        record = self.page.load_record(
            501
        )

        self.assertEqual(
            record[
                "survey_record_id"
            ],
            501,
        )

        mock_live_canals.assert_called_with(
            20,
            active_only=False,
        )
        mock_canal_unit.assert_called_with(
            30
        )
        mock_scope_snapshot.assert_called_once_with(
            "task-history",
            "scope-history",
        )

        self.assertEqual(
            self.page.canal_combo.count(),
            1,
        )
        self.assertEqual(
            self.page.canal_combo.currentData()[
                "id"
            ],
            30,
        )
        self.assertEqual(
            self.page.canal_combo.currentText(),
            "总干渠",
        )

        # 页面本身在 offscreen 测试中没有 show()；
        # QWidget.isVisible() 会受祖先窗口隐藏状态影响。
        # 这里验证控件自身没有被 hide() 即可。
        self.assertFalse(
            self.page.task_scope_combo.isHidden()
        )
        self.assertEqual(
            self.page.task_scope_combo.count(),
            1,
        )
        self.assertEqual(
            self.page.task_scope_combo.currentData()[
                "management_scope_uid"
            ],
            "scope-history",
        )
        self.assertIn(
            "边界未知",
            self.page.task_scope_combo.currentText(),
        )
        self.assertIn(
            "下发时冻结分管段",
            self.page.task_scope_combo.currentText(),
        )

        self.assertFalse(
            self.page.department_combo.isEnabled()
        )
        self.assertFalse(
            self.page.office_combo.isEnabled()
        )
        self.assertFalse(
            self.page.canal_combo.isEnabled()
        )
        self.assertFalse(
            self.page.task_scope_combo.isEnabled()
        )



if __name__ == "__main__":
    unittest.main()
