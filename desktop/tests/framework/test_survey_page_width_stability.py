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


from PySide6.QtCore import QPoint
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QSizePolicy,
)

from forms.engineering.registry import (
    get_engineering_form_definitions,
)
from pages.components.engineering_survey_list_page import (
    EngineeringSurveyListPage,
)
from pages.components.generic_engineering_survey_page import (
    GenericEngineeringSurveyPage,
)
from pages.survey_page import SurveyPage
from styles.app_theme import APP_QSS


class SurveyPageWidthStabilityTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def setUp(self):
        # Construct real widgets without loading unrelated survey data.
        load_data_patch = patch.object(
            EngineeringSurveyListPage,
            "load_data",
            autospec=True,
        )
        load_data_patch.start()
        self.addCleanup(load_data_patch.stop)

        # Fail before opening SQLite if another widget adds a database query.
        database_patch = patch(
            "database.get_connection",
            side_effect=AssertionError(
                "Survey width tests must not access SQLite."
            ),
        )
        database_patch.start()
        self.addCleanup(database_patch.stop)

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

    def test_all_14_lists_scroll_without_expanding_the_survey_stack(self):
        page = SurveyPage()
        try:
            page.setStyleSheet(APP_QSS)
            page.resize(1040, 560)
            page.show()
            self.app.processEvents()
            self.assertEqual(len(page.engineering_pages), 14)
            self.assertEqual(page.width(), 1040)
            page.resize(760, 560)
            self.app.processEvents()
            for pages in page.engineering_pages.values():
                listing = pages["list_page"]
                with self.subTest(form_code=listing.FORM_CODE):
                    listing._update_statistics([])
                    page.stack.setCurrentWidget(listing)
                    self.app.processEvents()
                    area = listing.scroll_area
                    self.assertTrue(area.widgetResizable())
                    self.assertEqual(
                        area.sizeAdjustPolicy(),
                        QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored,
                    )
                    self.assertEqual(page.width(), 760)
                    self.assertEqual(area.horizontalScrollBar().maximum(), 0)
                    self.assertGreater(area.verticalScrollBar().maximum(), 0)
                    self.assertGreaterEqual(listing.table.height(), 300)
                    bar = area.verticalScrollBar()
                    bar.setValue(bar.maximum())
                    self.app.processEvents()
                    bottom = listing.table.mapTo(
                        area.viewport(), QPoint(0, listing.table.height())
                    )
                    self.assertLessEqual(bottom.y(), area.viewport().height())
                    page.stack.setCurrentWidget(pages["edit_page"])
                    self.app.processEvents()
                    self.assertEqual(page.width(), 760)
        finally:
            page.close()
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
