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


from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
)

from pages.home_page import HomePage
from services.runtime_paths import get_resource_path


class ProductionShellTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def test_home_page_shows_scope_and_context(self):
        with (
            patch(
                "pages.home_page.get_current_context",
                return_value={
                    "project_name": "测试项目",
                    "batch_name": "测试批次",
                },
            ),
            patch(
                "pages.home_page.get_survey_readiness",
                return_value={
                    "ready": True,
                    "missing": [],
                },
            ),
        ):
            page = HomePage()

        try:
            label_text = " ".join(
                label.text()
                for label in page.findChildren(QLabel)
            )

            self.assertIn("测试项目", label_text)
            self.assertIn("测试批次", label_text)
            self.assertIn("附表2.1～2.14", label_text)
            self.assertIn("附表1.1～1.15", label_text)
        finally:
            page.deleteLater()

    def test_home_page_quick_actions(self):
        with (
            patch(
                "pages.home_page.get_current_context",
                return_value=None,
            ),
            patch(
                "pages.home_page.get_survey_readiness",
                return_value={
                    "ready": False,
                    "missing": ["项目"],
                },
            ),
        ):
            page = HomePage()

        try:
            buttons = {
                button.text()
                for button in page.findChildren(QPushButton)
            }

            self.assertEqual(
                buttons,
                {
                    "开始调查录入",
                    "查看工程台账",
                    "查询调查数据",
                    "提交调查成果",
                },
            )

            received = []
            page.navigate_requested.connect(
                received.append
            )

            query_button = next(
                button
                for button in page.findChildren(QPushButton)
                if button.text() == "查询调查数据"
            )
            query_button.click()

            self.assertEqual(
                received,
                ["数据查询"],
            )
        finally:
            page.deleteLater()

    def test_application_icon_resource_exists(self):
        icon_path = get_resource_path(
            "assets",
            "app_icon.ico",
        )

        self.assertTrue(
            icon_path.exists(),
            str(icon_path),
        )


if __name__ == "__main__":
    unittest.main()
