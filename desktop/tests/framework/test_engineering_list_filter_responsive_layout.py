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


from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QScrollArea,
)

from pages.components.engineering_survey_list_page import (
    EngineeringSurveyListPage,
)
from styles.app_theme import APP_QSS


class _TestEngineeringListPage(
    EngineeringSurveyListPage,
):
    FORM_CODE = "form_test"
    PAGE_TITLE = "测试工程记录"
    TABLE_HEADERS = (
        "编号",
        "名称",
    )
    TABLE_WIDTHS = (
        120,
        160,
    )
    GRADE_OPTIONS = (
        "A",
        "B",
        "C",
        "D",
    )


class EngineeringListFilterResponsiveLayoutTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def _make_page(self):
        context = {
            "project_id": 1,
            "batch_id": 1,
        }

        with (
            patch(
                "pages.components.engineering_survey_list_page"
                ".get_current_context",
                return_value=context,
            ),
            patch.object(
                _TestEngineeringListPage,
                "_load_records",
                return_value=[],
            ),
        ):
            return _TestEngineeringListPage()

    def test_range_filters_use_two_row_grid(
        self,
    ):
        page = self._make_page()

        try:
            range_grid = page.findChild(
                QGridLayout,
                "filterRangeGrid",
            )

            self.assertIsNotNone(
                range_grid
            )

            self.assertIs(
                (
                    range_grid
                    .itemAtPosition(0, 2)
                    .widget()
                ),
                page.keyword_edit,
            )

            self.assertIs(
                (
                    range_grid
                    .itemAtPosition(0, 4)
                    .widget()
                ),
                page.department_filter,
            )

            self.assertIs(
                (
                    range_grid
                    .itemAtPosition(1, 2)
                    .widget()
                ),
                page.office_filter,
            )

            self.assertIs(
                (
                    range_grid
                    .itemAtPosition(1, 4)
                    .widget()
                ),
                page.canal_filter,
            )

        finally:
            page.deleteLater()

    def test_status_filters_use_separate_grid(
        self,
    ):
        page = self._make_page()

        try:
            status_grid = page.findChild(
                QGridLayout,
                "filterStatusGrid",
            )

            self.assertIsNotNone(
                status_grid
            )

            self.assertIs(
                (
                    status_grid
                    .itemAtPosition(0, 2)
                    .widget()
                ),
                page.status_filter,
            )

            self.assertIs(
                (
                    status_grid
                    .itemAtPosition(0, 4)
                    .widget()
                ),
                page.grade_filter,
            )

        finally:
            page.deleteLater()

    def test_shared_filter_width_roles_are_preserved(
        self,
    ):
        page = self._make_page()

        try:
            for widget in (
                page.keyword_edit,
                page.department_filter,
                page.office_filter,
                page.canal_filter,
                page.status_filter,
                page.grade_filter,
            ):
                self.assertEqual(
                    widget.property(
                        "uiWidthRole"
                    ),
                    "filter",
                )
        finally:
            page.deleteLater()

    def _show_page(self, height=360, width=1040):
        page = self._make_page()
        self.addCleanup(page.deleteLater)
        self.addCleanup(page.close)
        page.setStyleSheet(APP_QSS)
        page.resize(width, height)
        page.show()
        self.app.processEvents()
        return page

    def _scroll_area(self, page):
        area = page.findChild(QScrollArea)
        self.assertIsNotNone(area, "The list needs its own page scroll area")
        return area

    def test_small_viewport_can_reach_table_without_squeezing_it(self):
        page = self._show_page(width=760)
        area = self._scroll_area(page)
        self.assertEqual(page.height(), 360)
        self.assertGreaterEqual(page.table.minimumHeight(), 280)
        self.assertLessEqual(page.table.minimumHeight(), 320)
        self.assertGreaterEqual(page.table.height(), page.table.minimumHeight())
        self.assertGreater(area.verticalScrollBar().maximum(), 0)
        self.assertEqual(area.horizontalScrollBar().maximum(), 0)

        area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
        self.app.processEvents()
        bottom = page.table.mapTo(area.viewport(), QPoint(0, page.table.height()))
        self.assertLessEqual(bottom.y(), area.viewport().height())
        self.assertGreater(bottom.y(), 0)

    def test_tall_viewport_expands_table_and_removes_page_scrollbar(self):
        page = self._show_page(height=1000)
        area = self._scroll_area(page)
        self.assertEqual(area.verticalScrollBar().maximum(), 0)
        initial_height = page.table.height()
        self.assertGreater(initial_height, page.table.minimumHeight())

        page.resize(1040, 1200)
        self.app.processEvents()
        self.assertGreaterEqual(page.table.height() - initial_height, 190)
        self.assertEqual(area.verticalScrollBar().maximum(), 0)

    def test_row_counts_keep_page_height_bounded_and_table_scrolls_internally(self):
        page = self._show_page()
        area = self._scroll_area(page)
        table_height = page.table.height()
        page_range = area.verticalScrollBar().maximum()
        for count in (0, 1, 20, 2000):
            with self.subTest(count=count):
                page.table.setRowCount(count)
                self.app.processEvents()
                self.assertEqual(page.table.height(), table_height)
                self.assertEqual(area.verticalScrollBar().maximum(), page_range)
                if count >= 20:
                    bar = page.table.verticalScrollBar()
                    self.assertGreater(bar.maximum(), 0)
                    bar.setValue(bar.maximum())
                    self.assertEqual(bar.value(), bar.maximum())

    def test_default_wheel_and_focus_can_reach_both_ends_of_page(self):
        page = self._show_page()
        area = self._scroll_area(page)
        position = QPointF(10, 10)
        event = QWheelEvent(
            position, QPointF(area.viewport().mapToGlobal(QPoint(10, 10))),
            QPoint(), QPoint(0, -120), Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False,
        )
        self.app.sendEvent(area.viewport(), event)
        self.assertGreater(area.verticalScrollBar().value(), 0)

        page.table.setFocus()
        self.app.processEvents()
        self.assertGreater(area.verticalScrollBar().value(), 0)
        page.keyword_edit.setFocus()
        self.app.processEvents()
        top = page.keyword_edit.mapTo(area.viewport(), QPoint())
        self.assertGreaterEqual(top.y(), 0)
        self.assertLess(top.y(), area.viewport().height())


if __name__ == "__main__":
    unittest.main()
