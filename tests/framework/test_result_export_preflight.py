import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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
)

from pages.result_export_page import (
    ResultExportPage,
)
from services.engineering_result_preflight import (
    BatchPreflightReport,
    PreflightIssue,
)


class ResultExportPreflightUiTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def setUp(self):
        self.patches = [
            patch(
                "pages.result_export_page."
                "get_current_context",
                return_value={
                    "project_id": 1,
                    "project_name": "测试项目",
                    "batch_id": 2,
                    "batch_name": (
                        "2026年度全面调查"
                    ),
                },
            ),
            patch(
                "pages.result_export_page."
                "get_departments",
                return_value=[],
            ),
            patch(
                "pages.result_export_page."
                "get_water_offices",
                return_value=[],
            ),
            patch(
                "pages.result_export_page."
                "get_canal_units",
                return_value=[],
            ),
            patch(
                "pages.result_export_page."
                "get_engineering_form_definitions",
                return_value=(),
            ),
        ]

        for current_patch in self.patches:
            current_patch.start()

        self.page = ResultExportPage()

    def tearDown(self):
        self.page.deleteLater()

        for current_patch in reversed(
            self.patches
        ):
            current_patch.stop()

    def test_preflight_error_blocks_export_confirmation(
        self,
    ):
        report = BatchPreflightReport(
            issues=(
                PreflightIssue(
                    severity="error",
                    code=(
                        "MISSING_MANAGED_FILE"
                    ),
                    message="托管文件缺失",
                    survey_record_id=1,
                    business_code=(
                        "1-01-03-02-001"
                    ),
                ),
            )
        )

        fake_plan = SimpleNamespace(
            records=(
                {
                    "survey_record_id": 1,
                },
            ),
            groups=(),
        )

        with tempfile.TemporaryDirectory() as temp:
            self.page.output_parent_edit.setText(
                temp
            )

            with patch(
                "pages.result_export_page."
                "build_batch_export_plan",
                return_value=fake_plan,
            ), patch(
                "pages.result_export_page."
                "inspect_batch_export_plan",
                return_value=report,
            ), patch(
                "pages.result_export_page."
                "QMessageBox.warning",
            ) as warning, patch(
                "pages.result_export_page."
                "QMessageBox.question",
            ) as question:
                self.page.start_export()

        warning.assert_called_once()
        question.assert_not_called()

        self.assertEqual(
            self.page.status_label.text(),
            "成果预检未通过。",
        )


if __name__ == "__main__":
    unittest.main()
