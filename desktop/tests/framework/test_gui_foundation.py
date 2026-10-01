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
    sys.path.insert(0, str(SRC_DIR))


from PySide6.QtWidgets import (
    QApplication,
    QPushButton,
)

from pages.canal_page import CanalPage
from styles.app_theme import APP_QSS


class GuiFoundationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def test_global_theme_contains_shell_and_common_controls(self):
        for selector in (
            "QFrame#sidebar",
            "QPushButton#navButton",
            "QFrame#contentCard",
            "QTableWidget",
            "QTreeWidget",
            "QTabBar::tab:selected",
            'QPushButton[role="danger"]',
        ):
            self.assertIn(
                selector,
                APP_QSS,
            )

    def test_main_loads_application_theme(self):
        source = (
            PROJECT_ROOT
            / "src"
            / "main.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "from styles.app_theme import APP_QSS",
            source,
        )
        self.assertIn(
            "app.setStyleSheet(APP_QSS)",
            source,
        )
        self.assertNotIn(
            "self.setStyleSheet",
            source,
        )

    @patch(
        "pages.canal_page.get_canal_sort_order_map",
        return_value={},
    )
    @patch(
        "pages.canal_page.get_canal_units",
        return_value=[],
    )
    def test_canal_primary_button_order(
        self,
        _mock_canals,
        _mock_sort,
    ):
        page = CanalPage()

        try:
            button_layout = (
                page.layout()
                .itemAt(1)
                .layout()
            )

            texts = []

            for index in range(
                button_layout.count()
            ):
                widget = (
                    button_layout
                    .itemAt(index)
                    .widget()
                )

                if isinstance(
                    widget,
                    QPushButton,
                ):
                    texts.append(
                        widget.text()
                    )

            self.assertEqual(
                texts,
                [
                    "新增渠道",
                    "编辑选中",
                    "管理分管段",
                    "停用选中",
                    "删除选中",
                    "刷新",
                ],
            )

        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
