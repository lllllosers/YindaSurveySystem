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

    def test_task_received_refreshes_page_and_emits_context_changed(self):
        """
        任务接收已经从 SurveyTaskPage 拆成独立页面。

        本测试验证新的职责边界：
        1. SurveyTaskPage 不再持有 task_receive_panel；
        2. SurveyTaskReceivePage 将 task_received 转发为 context_changed；
        3. MainWindow 收到 context_changed 后刷新当前项目/调查批次上下文。
        """
        from pathlib import Path

        project_root = Path(__file__).resolve().parents[2]

        issue_page_source = (
            project_root
            / "src"
            / "pages"
            / "survey_task_page.py"
        ).read_text(
            encoding="utf-8"
        )

        receive_page_source = (
            project_root
            / "src"
            / "pages"
            / "survey_task_receive_page.py"
        ).read_text(
            encoding="utf-8"
        )

        main_source = (
            project_root
            / "src"
            / "main.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "self.task_receive_panel",
            issue_page_source,
        )

        self.assertIn(
            "self.task_receive_panel.task_received.connect(",
            receive_page_source,
        )
        self.assertIn(
            "self.context_changed.emit",
            receive_page_source,
        )

        self.assertIn(
            "self.survey_task_receive_page.context_changed.connect(",
            main_source,
        )
        self.assertIn(
            "self.refresh_current_context",
            main_source,
        )

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
