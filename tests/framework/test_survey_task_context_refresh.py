import os
import sys
import unittest
from pathlib import Path
from unittest.mock import (
    MagicMock,
    patch,
)


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


from PySide6.QtWidgets import QApplication

from pages.survey_task_page import SurveyTaskPage


class SurveyTaskContextRefreshTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    @patch(
        "pages.components."
        "survey_task_receive_panel."
        "get_current_task_workspace",
        return_value=None,
    )
    @patch(
        "pages.survey_task_page."
        "get_canal_units_for_organization",
        return_value=[],
    )
    @patch(
        "pages.survey_task_page."
        "get_water_offices",
        return_value=[],
    )
    @patch(
        "pages.survey_task_page."
        "get_departments",
        return_value=[],
    )
    @patch(
        "pages.survey_task_page."
        "get_current_context",
        return_value=None,
    )
    def test_task_received_refreshes_page_and_emits_context_changed(
        self,
        *mocks,
    ):
        page = SurveyTaskPage()

        try:
            page.reload_context = (
                MagicMock()
            )

            emitted = []
            page.context_changed.connect(
                lambda: emitted.append(
                    True
                )
            )

            page.task_receive_panel.task_received.emit()

            page.reload_context.assert_called_once_with()
            self.assertEqual(
                emitted,
                [True],
            )
        finally:
            page.deleteLater()

    def test_main_window_connects_task_context_signal(
        self,
    ):
        main_path = (
            PROJECT_ROOT
            / "src"
            / "main.py"
        )

        text = main_path.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            (
                "self.survey_task_page."
                "context_changed.connect"
            ),
            text,
        )

        self.assertIn(
            (
                "self.refresh_current_context()"
            ),
            text[
                text.index(
                    "def change_page"
                ):
                text.index(
                    "def closeEvent"
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
