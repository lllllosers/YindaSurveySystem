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


from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
)

from pages.components.engineering_survey_list_page import (
    EngineeringSurveyListPage,
)


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


if __name__ == "__main__":
    unittest.main()
