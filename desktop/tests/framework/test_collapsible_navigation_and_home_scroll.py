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
    QScrollArea,
)

from pages.home_page import HomePage


class CollapsibleNavigationAndHomeScrollTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def test_home_uses_scroll_container_and_bounded_progress_tree(
        self,
    ):
        with (
            patch(
                "pages.home_page.get_current_context",
                return_value=None,
            ),
            patch(
                "pages.home_page.get_survey_readiness",
                return_value={
                    "ready": False,
                    "missing": [],
                },
            ),
        ):
            page = HomePage()

        try:
            self.assertIsInstance(
                page.scroll_area,
                QScrollArea,
            )
            self.assertTrue(
                page.scroll_area.widgetResizable()
            )
            self.assertLessEqual(
                page.progress_tree.maximumHeight(),
                300,
            )
        finally:
            page.deleteLater()

    def test_main_uses_collapsible_second_level_navigation(
        self,
    ):
        source = (
            PROJECT_ROOT
            / "src"
            / "main.py"
        ).read_text(
            encoding="utf-8"
        )

        for expected in (
            "def _set_nav_group_expanded(",
            '"任务管理"',
            '"任务分发"',
            '"任务接收"',
            '"成果管理"',
            '"成果提交"',
            '"成果接收"',
        ):
            self.assertIn(
                expected,
                source,
            )

        self.assertNotIn(
            '"任务下发"',
            source,
        )


if __name__ == "__main__":
    unittest.main()
