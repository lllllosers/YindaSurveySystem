import os
import sys
import unittest
from pathlib import Path


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

from pages.components.survey_result_package_panel import (
    SurveyResultPackagePanel,
)


class SurveyResultPackageSimpleUiTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def test_manual_task_link_controls_are_removed(
        self,
    ):
        panel = SurveyResultPackagePanel(
            context_provider=lambda: None,
            scope_provider=lambda: None,
        )

        try:
            self.assertFalse(
                hasattr(
                    panel,
                    "choose_task_button",
                )
            )
            self.assertFalse(
                hasattr(
                    panel,
                    "clear_task_button",
                )
            )
            self.assertFalse(
                hasattr(
                    panel,
                    "task_value_label",
                )
            )
            self.assertFalse(
                hasattr(
                    panel,
                    "_source_task_uid",
                )
            )
            self.assertFalse(
                hasattr(
                    panel,
                    "_source_task_info",
                )
            )
        finally:
            panel.deleteLater()


if __name__ == "__main__":
    unittest.main()
