import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from PySide6.QtWidgets import QApplication

from forms.engineering.form_2_1 import FORM_2_1
from pages.components.engineering_field_runtime import (
    create_engineering_field_runtime,
)
from pages.components.engineering_survey_list_page import (
    EngineeringSurveyListPage,
)
from pages.survey_page import SurveyPage


class NavigationReturnAndChannelGradeTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def test_form_2_1_channel_grade_uses_structure_grade_runtime(
        self,
    ):
        field = FORM_2_1.field_map[
            "channel_grade"
        ]

        self.assertEqual(
            field.input_type,
            "structure_grade",
        )

        runtime = (
            create_engineering_field_runtime(
                field
            )
        )

        try:
            runtime.widget.setText("3")
            runtime.widget.editingFinished.emit()

            self.assertEqual(
                runtime.widget.text(),
                "3级",
            )
            self.assertEqual(
                runtime.get_value(),
                "3级",
            )
        finally:
            runtime.widget.deleteLater()

    @patch.object(
        EngineeringSurveyListPage,
        "load_data",
        return_value=None,
    )
    def test_external_record_back_returns_to_engineering_ledger(
        self,
        _mock_list_load,
    ):
        page = SurveyPage()

        try:
            edit_page = page.engineering_pages[
                "form_2_1"
            ]["edit_page"]

            with patch.object(
                edit_page,
                "load_record",
                return_value={},
            ):
                page.open_engineering_edit(
                    "form_2_1",
                    101,
                    return_page_name="工程台账",
                )

            received = []
            page.return_to_module_requested.connect(
                received.append
            )

            edit_page.back_requested.emit()

            self.assertEqual(
                received,
                ["工程台账"],
            )
            self.assertIsNone(
                page._external_return_page_name
            )
        finally:
            page.deleteLater()

    @patch.object(
        EngineeringSurveyListPage,
        "load_data",
        return_value=None,
    )
    def test_normal_survey_edit_back_stays_in_form_list(
        self,
        _mock_list_load,
    ):
        page = SurveyPage()

        try:
            edit_page = page.engineering_pages[
                "form_2_1"
            ]["edit_page"]
            list_page = page.engineering_pages[
                "form_2_1"
            ]["list_page"]

            with patch.object(
                edit_page,
                "load_record",
                return_value={},
            ):
                page.open_engineering_edit(
                    "form_2_1",
                    102,
                )

            edit_page.back_requested.emit()

            self.assertIs(
                page.stack.currentWidget(),
                list_page,
            )
        finally:
            page.deleteLater()

    def test_main_passes_explicit_return_origin(self):
        source = (
            PROJECT_ROOT
            / "src"
            / "main.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'return_page_name=return_page_name',
            source,
        )
        self.assertIn(
            'self.survey_page.return_to_module_requested.connect',
            source,
        )


if __name__ == "__main__":
    unittest.main()
