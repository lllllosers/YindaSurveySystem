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


from PySide6.QtWidgets import QApplication

from pages.result_receive_page import ResultReceivePage
from pages.survey_task_receive_page import (
    SurveyTaskReceivePage,
)


class WorkflowNavigationSplitTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    @patch(
        "pages.components.survey_task_receive_panel."
        "get_current_task_workspace",
        return_value=None,
    )
    def test_task_receive_has_dedicated_page(
        self,
        _mock_workspace,
    ):
        page = SurveyTaskReceivePage()

        try:
            self.assertIsNotNone(
                page.task_receive_panel
            )
        finally:
            page.deleteLater()

    def test_result_receive_has_dedicated_page(
        self,
    ):
        page = ResultReceivePage()

        try:
            self.assertIsNotNone(
                page.result_receive_panel
            )
        finally:
            page.deleteLater()

    def test_main_exposes_split_navigation(self):
        source = (
            PROJECT_ROOT
            / "src"
            / "main.py"
        ).read_text(
            encoding="utf-8"
        )

        for text in (
            "任务管理",
            "任务分发",
            "任务接收",
            "成果管理",
            "成果提交",
            "成果接收",
            "项目/批次",
        ):
            self.assertIn(
                text,
                source,
            )

        self.assertNotIn(
            '"项目与批次"',
            source,
        )

    def test_mixed_pages_no_longer_own_receive_panels(
        self,
    ):
        task_source = (
            PROJECT_ROOT
            / "src"
            / "pages"
            / "survey_task_page.py"
        ).read_text(
            encoding="utf-8"
        )
        result_source = (
            PROJECT_ROOT
            / "src"
            / "pages"
            / "result_export_page.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "SurveyTaskReceivePanel",
            task_source,
        )
        self.assertNotIn(
            "SurveyResultReceivePanel",
            result_source,
        )


if __name__ == "__main__":
    unittest.main()
