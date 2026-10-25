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
from forms.engineering.form_2_2 import FORM_2_2
from main import MainWindow
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

    def _make_sluice_main_window(self, count):
        context = dict(
            project_id=1, batch_id=1,
            project_name="布局测试项目", batch_name="布局测试批次",
        )
        with (
            patch("main.get_current_context", return_value=context),
            patch("main.HomePage.refresh_data"),
            patch.object(MainWindow, "can_start_survey", return_value=True),
        ):
            window = MainWindow()
            window.change_page("调查录入")
            window.survey_page.open_engineering_list(FORM_2_2.form_code)
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        window.setStyleSheet(APP_QSS)
        listing = window.survey_page.engineering_pages[FORM_2_2.form_code]["list_page"]
        listing.all_records = [dict(
            survey_record_id=i + 1, business_code=f"TEST-{i+1:03d}",
            asset_name="测试水闸", department_name="测试处", office_name="测试所",
            canal_name="测试渠", engineering_position="CH1+000.000～CH1+010.000",
            overall_grade="B", record_status="draft", survey_date=None,
            updated_at=None, record_data={},
        ) for i in range(count)]
        listing.apply_filters()
        window.resize(1200, 760)
        window.show()
        self.app.processEvents()
        return window, listing

    def test_sluice_table_is_reachable_in_real_main_window_with_zero_or_20_rows(self):
        for count in (0, 20):
            with self.subTest(count=count):
                window, listing = self._make_sluice_main_window(count)
                area, table = listing.scroll_area, listing.table
                bar = area.verticalScrollBar()
                self.assertEqual(window.width(), 1200)
                self.assertEqual(table.rowCount(), count)
                self.assertEqual(table.minimumHeight(), 300)
                self.assertGreaterEqual(table.height(), 300)
                self.assertGreater(bar.maximum(), 0)
                self.assertEqual(
                    bar.maximum(), area.widget().height() - area.viewport().height()
                )
                card = window.content_layout.parentWidget()
                area_rect = area.rect()
                area_rect.moveTopLeft(area.mapTo(card, QPoint()))
                self.assertTrue(card.rect().contains(area_rect))

                bar.setValue(bar.maximum())
                self.app.processEvents()
                table_rect = table.rect()
                table_rect.moveTopLeft(table.mapTo(area.viewport(), QPoint()))
                self.assertTrue(area.viewport().rect().contains(table_rect))
                outer_position = bar.value()
                self.assertGreater(table.horizontalScrollBar().maximum(), 0)
                table.horizontalScrollBar().setValue(table.horizontalScrollBar().maximum())
                if count:
                    inner = table.verticalScrollBar()
                    self.assertGreater(inner.maximum(), 0)
                    inner.setValue(inner.maximum())
                    self.app.processEvents()
                    last = table.item(count - 1, table.columnCount() - 1)
                    self.assertTrue(table.viewport().rect().contains(table.visualItemRect(last).center()))
                self.assertEqual(bar.value(), outer_position)
                bar.setValue(0)
                self.app.processEvents()
                keyword = listing.keyword_edit.mapTo(area.viewport(), QPoint())
                self.assertTrue(area.viewport().rect().contains(keyword))
                window.close()

    def test_sluice_table_expands_and_recovers_after_main_window_resize(self):
        for count in (0, 20):
            with self.subTest(count=count):
                window, listing = self._make_sluice_main_window(count)
                window.resize(1800, 1100)
                self.app.processEvents()
                self.assertEqual(window.width(), 1800)
                self.assertEqual(listing.scroll_area.verticalScrollBar().maximum(), 0)
                self.assertGreater(listing.table.height(), 300)
                window.resize(1200, 760)
                self.app.processEvents()
                self.assertEqual(window.width(), 1200)
                self.assertEqual(listing.table.height(), 300)
                bar = listing.scroll_area.verticalScrollBar()
                self.assertGreater(bar.maximum(), 0)
                bar.setValue(bar.maximum())
                self.app.processEvents()
                bottom = listing.table.mapTo(
                    listing.scroll_area.viewport(), QPoint(0, listing.table.height())
                )
                self.assertEqual(bottom.y(), listing.scroll_area.viewport().height())
                window.close()


if __name__ == "__main__":
    unittest.main()
