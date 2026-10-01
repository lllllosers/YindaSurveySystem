import os
import sys
import unittest
from pathlib import Path


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

from forms.engineering.form_2_2 import (
    FORM_2_2,
)
from forms.engineering.form_2_10 import (
    FORM_2_10,
)
from forms.engineering.grading import (
    get_worst_grade,
)
from pages.components.generic_engineering_survey_page import (
    GenericEngineeringSurveyPage,
)


class EngineeringOverallGradeTestCase(
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

    def test_worst_grade_four_levels(
        self,
    ):
        self.assertEqual(
            get_worst_grade(
                ("A", "B", "C", "D"),
                ("A", "A", "B", "A"),
            ),
            "B",
        )

        self.assertEqual(
            get_worst_grade(
                ("A", "B", "C", "D"),
                ("A", "C", "B"),
            ),
            "C",
        )

        self.assertEqual(
            get_worst_grade(
                ("A", "B", "C", "D"),
                ("A", "D", "B"),
            ),
            "D",
        )

    def test_worst_grade_three_levels(
        self,
    ):
        self.assertEqual(
            get_worst_grade(
                ("A", "B", "C"),
                ("A", "B", "C"),
            ),
            "C",
        )

        self.assertIsNone(
            get_worst_grade(
                ("A", "B", "C"),
                (),
            )
        )

    def test_unknown_grade_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "定义外",
        ):
            get_worst_grade(
                ("A", "B", "C"),
                ("D",),
            )

    def test_auto_grade_tracks_worst_selected_item(
        self,
    ):
        page = GenericEngineeringSurveyPage(
            FORM_2_2
        )

        try:
            self.assertTrue(
                page.auto_overall_grade_checkbox
                .isChecked()
            )

            item_codes = [
                item["item_code"]
                for item
                in FORM_2_2.evaluation_items
            ]

            page.evaluation_section.grade_buttons[
                item_codes[0]
            ]["A"].click()

            self.assertEqual(
                page.get_overall_grade(),
                "A",
            )

            page.evaluation_section.grade_buttons[
                item_codes[1]
            ]["B"].click()

            self.assertEqual(
                page.get_overall_grade(),
                "B",
            )

            page.evaluation_section.grade_buttons[
                item_codes[2]
            ]["C"].click()

            self.assertEqual(
                page.get_overall_grade(),
                "C",
            )

        finally:
            page.deleteLater()

    def test_manual_override_stops_auto_until_reenabled(
        self,
    ):
        page = GenericEngineeringSurveyPage(
            FORM_2_2
        )

        try:
            item_codes = [
                item["item_code"]
                for item
                in FORM_2_2.evaluation_items
            ]

            page.evaluation_section.grade_buttons[
                item_codes[0]
            ]["B"].click()

            self.assertEqual(
                page.get_overall_grade(),
                "B",
            )

            page.overall_grade_buttons[
                "A"
            ].click()

            self.assertFalse(
                page.auto_overall_grade_checkbox
                .isChecked()
            )
            self.assertEqual(
                page.get_overall_grade(),
                "A",
            )

            page.evaluation_section.grade_buttons[
                item_codes[1]
            ]["D"].click()

            self.assertEqual(
                page.get_overall_grade(),
                "A",
            )

            page.auto_overall_grade_checkbox.click()

            self.assertTrue(
                page.auto_overall_grade_checkbox
                .isChecked()
            )
            self.assertEqual(
                page.get_overall_grade(),
                "D",
            )

        finally:
            page.deleteLater()

    def test_three_grade_form_auto_never_introduces_d(
        self,
    ):
        page = GenericEngineeringSurveyPage(
            FORM_2_10
        )

        try:
            self.assertNotIn(
                "D",
                page.overall_grade_buttons,
            )

            first_item = (
                FORM_2_10
                .evaluation_items[0]
                ["item_code"]
            )

            page.evaluation_section.grade_buttons[
                first_item
            ]["C"].click()

            self.assertEqual(
                page.get_overall_grade(),
                "C",
            )

        finally:
            page.deleteLater()

    def test_load_existing_record_infers_manual_override(
        self,
    ):
        page = GenericEngineeringSurveyPage(
            FORM_2_2
        )

        try:
            inspections = [
                {
                    "item_code": (
                        item["item_code"]
                    ),
                    "category": (
                        item["category"]
                    ),
                    "item_name": (
                        item["item_name"]
                    ),
                    "grade": "B",
                    "description": None,
                    "remark": None,
                }
                for item
                in FORM_2_2.evaluation_items
            ]

            page.load_form_data(
                record_data={},
                inspection_results=inspections,
                survey_date="2026-09-17",
                overall_grade="A",
                survey_comment="人工覆盖测试。",
            )

            self.assertFalse(
                page.auto_overall_grade_checkbox
                .isChecked()
            )
            self.assertEqual(
                page.get_overall_grade(),
                "A",
            )

            page.load_form_data(
                record_data={},
                inspection_results=inspections,
                survey_date="2026-09-17",
                overall_grade="B",
                survey_comment="自动判定测试。",
            )

            self.assertTrue(
                page.auto_overall_grade_checkbox
                .isChecked()
            )
            self.assertEqual(
                page.get_overall_grade(),
                "B",
            )

        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
