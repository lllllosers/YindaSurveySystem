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
    QLayout,
    QScrollArea,
)

from pages.result_export_page import (
    ResultExportPage,
)


class ResultExportScrollLayoutTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    @patch(
        "pages.result_export_page."
        "get_current_context",
        return_value=None,
    )
    def test_result_export_page_uses_vertical_scroll_container(
        self,
        mock_context,
    ):
        page = ResultExportPage()

        try:
            self.assertIsInstance(
                page.scroll_area,
                QScrollArea,
            )
            self.assertTrue(
                page.scroll_area.widgetResizable()
            )
            self.assertIsNotNone(
                page.scroll_area.widget()
            )
            self.assertEqual(
                (
                    page.scroll_area.widget()
                    .layout()
                    .sizeConstraint()
                ),
                QLayout.SizeConstraint.SetMinimumSize,
            )
        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
