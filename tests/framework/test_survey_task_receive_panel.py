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

from pages.components.survey_task_receive_panel import (
    SurveyTaskReceivePanel,
)


class SurveyTaskReceivePanelTestCase(
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
    def test_no_current_task_is_displayed_cleanly(
        self,
        mock_current,
    ):
        panel = SurveyTaskReceivePanel()

        try:
            self.assertEqual(
                panel.task_name_label.text(),
                "未接收调查任务",
            )
            self.assertIn(
                "没有已激活",
                panel.status_label.text(),
            )
        finally:
            panel.deleteLater()

    @patch(
        "pages.components."
        "survey_task_receive_panel."
        "get_current_task_workspace"
    )
    def test_current_task_scope_summary_is_displayed(
        self,
        mock_current,
    ):
        mock_current.return_value = {
            "task_name": (
                "通远水管所调查任务"
            ),
            "project_name": (
                "2026年调查项目"
            ),
            "batch_name": (
                "2026年调查批次"
            ),
            "organization_name": (
                "通远水管所"
            ),
            "received_at": (
                "2026-09-17 18:00:00"
            ),
            "management_scopes": (
                {
                    "canal_name": (
                        "通远支渠"
                    ),
                    "range_mode": "whole",
                },
                {
                    "canal_name": (
                        "总干渠"
                    ),
                    "range_mode": (
                        "segment_unknown"
                    ),
                },
            ),
        }

        panel = SurveyTaskReceivePanel()

        try:
            self.assertEqual(
                panel.task_name_label.text(),
                "通远水管所调查任务",
            )
            self.assertIn(
                "2026年调查项目",
                panel.project_batch_label.text(),
            )
            self.assertEqual(
                panel.organization_label.text(),
                "通远水管所",
            )
            self.assertIn(
                "通远支渠（全渠）",
                panel.scope_summary_label.text(),
            )
            self.assertIn(
                "总干渠（边界未知）",
                panel.scope_summary_label.text(),
            )
        finally:
            panel.deleteLater()


if __name__ == "__main__":
    unittest.main()
