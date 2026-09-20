import os
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from PySide6.QtWidgets import QApplication
from forms.engineering.form_2_2 import FORM_2_2
from pages.components.generic_engineering_survey_page import GenericEngineeringSurveyPage
from pages.survey_task_page import SurveyTaskPage


def _sqlite_rows(rows):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE offices (
            id INTEGER,
            parent_id INTEGER,
            name TEXT,
            unit_type TEXT,
            business_code TEXT,
            status TEXT,
            sort_order INTEGER,
            organization_unit_uid TEXT
        )
        """
    )
    connection.executemany(
        """
        INSERT INTO offices (
            id, parent_id, name, unit_type, business_code,
            status, sort_order, organization_unit_uid
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    result = connection.execute(
        "SELECT * FROM offices ORDER BY id"
    ).fetchall()
    connection.close()
    return result


class V111DepartmentWorkspaceUiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _parent_workspace(self):
        return {
            "task_uid": "T1",
            "root_task_uid": "T1",
            "parent_task_uid": None,
            "task_depth": 0,
            "target_unit_type": "department",
            "organization_unit_id": 10,
            "organization_unit_uid": "dept-uid",
            "organization_name": "测试处",
            "department_id": 10,
            "project_id": 1,
            "survey_batch_id": 2,
            "management_scopes": (
                {
                    "management_scope_uid": "scope-a",
                    "organization_unit_uid": "office-a",
                    "canal_unit_id": 101,
                    "canal_name": "A支渠",
                    "canal_level": "03",
                    "range_mode": "whole",
                    "sort_order": 1,
                    "status": "active",
                    "description": "",
                },
                {
                    "management_scope_uid": "scope-b",
                    "organization_unit_uid": "office-b",
                    "canal_unit_id": 202,
                    "canal_name": "B支渠",
                    "canal_level": "03",
                    "range_mode": "whole",
                    "sort_order": 2,
                    "status": "active",
                    "description": "",
                },
            ),
        }

    def _office_rows(self):
        return _sqlite_rows(
            [
                (20, 10, "A所", "water_office", "01", "active", 1, "office-a"),
                (21, 10, "B所", "water_office", "02", "active", 2, "office-b"),
            ]
        )

    @patch("pages.survey_task_page.list_survey_task_tracking", return_value=())
    @patch("pages.survey_task_page.get_canal_lineage", return_value=[])
    @patch("pages.survey_task_page.get_water_offices")
    @patch("pages.survey_task_page.get_current_task_workspace")
    @patch("pages.survey_task_page.get_current_context")
    def test_department_task_distribution_page_accepts_sqlite_rows(
        self,
        mock_context,
        mock_workspace,
        mock_offices,
        mock_lineage,
        mock_tracking,
    ):
        mock_context.return_value = {
            "project_id": 1,
            "project_name": "测试项目",
            "batch_id": 2,
            "batch_name": "测试批次",
        }
        mock_workspace.return_value = self._parent_workspace()
        mock_offices.return_value = self._office_rows()

        page = SurveyTaskPage()
        try:
            self.assertEqual(page._distribution_mode, "department")
            self.assertEqual(page.office_combo.count(), 2)
            self.assertEqual(page.office_combo.currentText(), "A所")
            self.assertEqual(page.canal_tree.topLevelItemCount(), 1)
            self.assertEqual(page.canal_tree.topLevelItem(0).text(1), "A支渠")
        finally:
            page.deleteLater()

    @patch(
        "pages.components.generic_engineering_survey_page."
        "get_engineering_business_codes",
        return_value=[],
    )
    @patch(
        "pages.components.generic_engineering_survey_page."
        "get_water_offices"
    )
    @patch(
        "pages.components.generic_engineering_survey_page."
        "get_departments"
    )
    def test_department_workspace_survey_entry_filters_by_selected_office(
        self,
        mock_departments,
        mock_offices,
        mock_codes,
    ):
        mock_departments.return_value = [
            {
                "id": 10,
                "name": "测试处",
                "business_code": "1",
                "status": "active",
            }
        ]
        mock_offices.return_value = self._office_rows()

        page = GenericEngineeringSurveyPage(FORM_2_2)
        try:
            page._entry_task_workspace = self._parent_workspace()
            page.current_context = {
                "project_id": 1,
                "batch_id": 2,
            }

            page.load_departments()

            self.assertEqual(page.office_combo.count(), 2)

            page.office_combo.setCurrentIndex(0)
            self.assertEqual(
                page.office_combo.currentData()["organization_unit_uid"],
                "office-a",
            )
            self.assertEqual(page.canal_combo.count(), 1)
            self.assertEqual(page.canal_combo.currentData()["id"], 101)
            self.assertEqual(page.task_scope_combo.count(), 1)
            self.assertEqual(
                page.task_scope_combo.currentData()["management_scope_uid"],
                "scope-a",
            )

            page.office_combo.setCurrentIndex(1)
            self.assertEqual(
                page.office_combo.currentData()["organization_unit_uid"],
                "office-b",
            )
            self.assertEqual(page.canal_combo.count(), 1)
            self.assertEqual(page.canal_combo.currentData()["id"], 202)
            self.assertEqual(page.task_scope_combo.count(), 1)
            self.assertEqual(
                page.task_scope_combo.currentData()["management_scope_uid"],
                "scope-b",
            )
        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
