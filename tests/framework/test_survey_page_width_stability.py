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
    QAbstractScrollArea,
    QApplication,
    QSizePolicy,
)

from forms.engineering.registry import (
    get_engineering_form_definitions,
)
from pages.components.generic_engineering_survey_page import (
    GenericEngineeringSurveyPage,
)
from pages.survey_page import SurveyPage


class SurveyPageWidthStabilityTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def test_survey_stack_does_not_force_hidden_page_width(
        self,
    ):
        page = SurveyPage()

        try:
            self.assertEqual(
                page.stack.sizePolicy().horizontalPolicy(),
                QSizePolicy.Policy.Ignored,
            )
            self.assertEqual(
                page.stack.minimumWidth(),
                0,
            )
        finally:
            page.deleteLater()

    def test_engineering_form_scroll_area_ignores_content_size_hint(
        self,
    ):
        definition = (
            get_engineering_form_definitions()[0]
        )

        page = GenericEngineeringSurveyPage(
            definition
        )

        try:
            self.assertEqual(
                page.scroll_area.sizeAdjustPolicy(),
                (
                    QAbstractScrollArea
                    .SizeAdjustPolicy
                    .AdjustIgnored
                ),
            )
            self.assertEqual(
                page.scroll_area.minimumWidth(),
                0,
            )
            self.assertEqual(
                page.form_container.minimumWidth(),
                0,
            )
        finally:
            page.deleteLater()

    def test_width_guard_is_applied_to_all_registered_edit_pages(
        self,
    ):
        page = SurveyPage()

        try:
            for pages in (
                page.engineering_pages.values()
            ):
                edit_page = pages["edit_page"]

                self.assertEqual(
                    (
                        edit_page.scroll_area
                        .sizeAdjustPolicy()
                    ),
                    (
                        QAbstractScrollArea
                        .SizeAdjustPolicy
                        .AdjustIgnored
                    ),
                )
                self.assertEqual(
                    edit_page.scroll_area.minimumWidth(),
                    0,
                )
        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
