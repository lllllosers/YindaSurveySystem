import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLineEdit
from pages.survey_task_page import SurveyTaskPage


class SurveyTaskPageTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @patch("pages.survey_task_page.get_canal_lineage")
    @patch("pages.survey_task_page.get_management_scopes_for_organization")
    @patch("pages.survey_task_page.get_water_offices")
    @patch("pages.survey_task_page.get_departments")
    @patch("pages.survey_task_page.get_current_context")
    def test_loads_context_and_shows_management_scopes(
        self,
        mock_context,
        mock_departments,
        mock_offices,
        mock_scopes,
        mock_lineage,
    ):
        mock_context.return_value = {
            "project_id": 1,
            "project_name": "测试项目",
            "batch_id": 2,
            "batch_name": "测试批次",
        }
        mock_departments.return_value = [
            {"id": 10, "name": "测试处", "status": "active", "sort_order": 100}
        ]
        mock_offices.return_value = [
            {"id": 20, "name": "测试管理单位", "status": "active", "sort_order": 101}
        ]
        mock_scopes.return_value = [
            {
                "id": 31,
                "management_scope_uid": "scope-b",
                "canal_unit_id": 31,
                "canal_name": "二支渠",
                "canal_level": "03",
                "canal_sort_order": 102,
                "range_mode": "segment_unknown",
                "start_stake_text": None,
                "start_stake_value": None,
                "end_stake_text": None,
                "end_stake_value": None,
                "sort_order": 2,
                "description": "",
                "status": "active",
            },
            {
                "id": 30,
                "management_scope_uid": "scope-a",
                "canal_unit_id": 30,
                "canal_name": "一支渠",
                "canal_level": "03",
                "canal_sort_order": 101,
                "range_mode": "segment_known",
                "start_stake_text": "K1+000",
                "start_stake_value": 1000.0,
                "end_stake_text": "K2+000",
                "end_stake_value": 2000.0,
                "sort_order": 1,
                "description": "备注",
                "status": "active",
            },
        ]

        def lineage(canal_id):
            canal_name = "一支渠" if canal_id == 30 else "二支渠"
            return [
                {"id": 1, "parent_id": None, "name": "总干渠", "canal_level": "01"},
                {"id": canal_id, "parent_id": 1, "name": canal_name, "canal_level": "03"},
            ]

        mock_lineage.side_effect = lineage
        page = SurveyTaskPage()
        try:
            self.assertEqual(page.project_label.text(), "测试项目")
            self.assertEqual(page.batch_label.text(), "测试批次")
            self.assertEqual(page.task_name_edit.text(), "测试管理单位调查任务")
            self.assertIsInstance(page.notes_edit, QLineEdit)
            self.assertEqual(page.canal_tree.columnCount(), 6)
            self.assertEqual(page.canal_tree.headerItem().text(2), "类型")
            self.assertEqual(page.canal_tree.headerItem().text(3), "管理范围")
            self.assertEqual(page.canal_tree.topLevelItemCount(), 2)

            first = page.canal_tree.topLevelItem(0)
            self.assertEqual(first.text(1), "一支渠")
            self.assertEqual(first.text(2), "分管段")
            self.assertEqual(first.text(3), "K1+000～K2+000")
            self.assertEqual(first.text(4), "总干渠")
            self.assertEqual(first.text(5), "备注")
            self.assertEqual(
                page.selected_management_scope_uids(),
                ("scope-a", "scope-b"),
            )
            self.assertEqual(page.scope_count_label.text(), "已选择 2 / 2 项")
        finally:
            page.deleteLater()

    @patch(
        "pages.survey_task_page.get_management_scopes_for_organization",
        return_value=[],
    )
    @patch("pages.survey_task_page.get_water_offices", return_value=[])
    @patch("pages.survey_task_page.get_departments", return_value=[])
    @patch("pages.survey_task_page.get_current_context", return_value=None)
    def test_no_context_disables_export(self, *mocks):
        page = SurveyTaskPage()
        try:
            self.assertFalse(page.export_button.isEnabled())
            self.assertEqual(page.project_label.text(), "未选择项目")
        finally:
            page.deleteLater()

    @patch("pages.survey_task_page.get_canal_lineage")
    @patch("pages.survey_task_page.get_management_scopes_for_organization")
    @patch("pages.survey_task_page.get_water_offices")
    @patch("pages.survey_task_page.get_departments")
    @patch("pages.survey_task_page.get_current_context")
    def test_clear_all_updates_selected_scope(
        self,
        mock_context,
        mock_departments,
        mock_offices,
        mock_scopes,
        mock_lineage,
    ):
        mock_context.return_value = {
            "project_id": 1,
            "project_name": "项目",
            "batch_id": 2,
            "batch_name": "批次",
        }
        mock_departments.return_value = [
            {"id": 10, "name": "处", "status": "active", "sort_order": 1}
        ]
        mock_offices.return_value = [
            {"id": 20, "name": "单位", "status": "active", "sort_order": 1}
        ]
        mock_scopes.return_value = [
            {
                "id": 30,
                "management_scope_uid": "scope-a",
                "canal_unit_id": 30,
                "canal_name": "支渠",
                "canal_level": "03",
                "canal_sort_order": 1,
                "range_mode": "whole",
                "start_stake_text": None,
                "start_stake_value": None,
                "end_stake_text": None,
                "end_stake_value": None,
                "sort_order": 1,
                "description": "",
                "status": "active",
            }
        ]
        mock_lineage.return_value = [
            {"id": 1, "parent_id": None, "name": "总干渠", "canal_level": "01"},
            {"id": 30, "parent_id": 1, "name": "支渠", "canal_level": "03"},
        ]
        page = SurveyTaskPage()
        try:
            page._set_all_checked(False)
            self.assertEqual(page.selected_management_scope_uids(), ())
            self.assertEqual(page.scope_count_label.text(), "已选择 0 / 1 项")
            self.assertEqual(
                page.canal_tree.topLevelItem(0).checkState(0),
                Qt.CheckState.Unchecked,
            )
        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
