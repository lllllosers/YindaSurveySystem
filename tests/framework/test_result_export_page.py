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

from forms.engineering.form_2_1 import (
    FORM_2_1,
)
from forms.engineering.form_2_2 import (
    FORM_2_2,
)
from pages.result_export_page import (
    ResultExportPage,
)


class ResultExportPageTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def setUp(self):
        self.patches = [
            patch(
                "pages.result_export_page."
                "get_current_context",
                return_value={
                    "project_id": 1,
                    "project_name": "测试项目",
                    "batch_id": 2,
                    "batch_name": (
                        "2026年度全面调查"
                    ),
                },
            ),
            patch(
                "pages.result_export_page."
                "get_departments",
                return_value=[
                    {
                        "id": 10,
                        "parent_id": None,
                        "name": "测试处",
                    }
                ],
            ),
            patch(
                "pages.result_export_page."
                "get_water_offices",
                return_value=[
                    {
                        "id": 11,
                        "parent_id": 10,
                        "name": "甲所",
                    },
                    {
                        "id": 12,
                        "parent_id": 10,
                        "name": "乙所",
                    },
                ],
            ),
            patch(
                "pages.result_export_page."
                "get_canal_units",
                return_value=[
                    {
                        "id": 20,
                        "parent_id": None,
                        "name": "总干渠",
                    },
                    {
                        "id": 21,
                        "parent_id": 20,
                        "name": "一支渠",
                    },
                ],
            ),
            patch(
                "pages.result_export_page."
                "get_engineering_form_definitions",
                return_value=(
                    FORM_2_1,
                    FORM_2_2,
                ),
            ),
        ]

        for current_patch in self.patches:
            current_patch.start()

        self.page = ResultExportPage()

    def tearDown(self):
        self.page.deleteLater()

        for current_patch in reversed(
            self.patches
        ):
            current_patch.stop()

    def test_page_uses_current_project_and_batch(
        self,
    ):
        self.assertEqual(
            self.page.project_value_label.text(),
            "测试项目",
        )
        self.assertEqual(
            self.page.batch_value_label.text(),
            "2026年度全面调查",
        )
        self.assertTrue(
            self.page.export_button.isEnabled()
        )

    def test_scope_defaults_to_completed_only(
        self,
    ):
        scope = self.page._build_scope()

        self.assertEqual(
            scope.project_id,
            1,
        )
        self.assertEqual(
            scope.survey_batch_id,
            2,
        )
        self.assertEqual(
            scope.record_statuses,
            ("completed",),
        )
        self.assertEqual(
            scope.organization_unit_ids,
            (),
        )
        self.assertEqual(
            scope.canal_unit_ids,
            (),
        )
        self.assertEqual(
            scope.form_codes,
            (),
        )

    def test_office_overrides_department_scope(
        self,
    ):
        department_index = (
            self.page.department_combo
            .findData(10)
        )

        self.page.department_combo.setCurrentIndex(
            department_index
        )

        office_index = (
            self.page.office_combo
            .findData(11)
        )

        self.page.office_combo.setCurrentIndex(
            office_index
        )

        scope = self.page._build_scope()

        self.assertEqual(
            scope.organization_unit_ids,
            (11,),
        )

    def test_canal_and_form_scope_are_explicit(
        self,
    ):
        canal_index = (
            self.page.canal_combo
            .findData(20)
        )

        self.page.canal_combo.setCurrentIndex(
            canal_index
        )

        form_index = (
            self.page.form_combo
            .findData("form_2_2")
        )

        self.page.form_combo.setCurrentIndex(
            form_index
        )

        self.page.include_canal_descendants_check.setChecked(
            False
        )

        scope = self.page._build_scope()

        self.assertEqual(
            scope.canal_unit_ids,
            (20,),
        )
        self.assertEqual(
            scope.form_codes,
            ("form_2_2",),
        )
        self.assertFalse(
            scope.include_canal_descendants
        )

    def test_canal_labels_include_parent_path(
        self,
    ):
        index = (
            self.page.canal_combo
            .findData(21)
        )

        self.assertGreaterEqual(
            index,
            0,
        )

        self.assertEqual(
            self.page.canal_combo.itemText(
                index
            ),
            "总干渠 / 一支渠",
        )


if __name__ == "__main__":
    unittest.main()
