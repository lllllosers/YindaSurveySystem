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

from pages.components.survey_result_receive_panel import (
    SurveyResultReceivePanel,
)
from services.survey_result_import_preflight import (
    SurveyResultImportPreflight,
)


class SurveyResultReceivePanelTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def _report(
        self,
        *,
        errors=(),
        new_records=2,
        existing_records=1,
    ):
        return SurveyResultImportPreflight(
            package_path=Path(
                "demo.ydresult"
            ),
            package_uid="package-1",
            result_uid="result-1",
            project_uid="project-1",
            survey_batch_uid="batch-1",
            new_assets=1,
            existing_assets=1,
            new_records=new_records,
            existing_records=(
                existing_records
            ),
            new_inspections=4,
            existing_inspections=2,
            new_media=3,
            existing_media=1,
            issues=tuple(
                errors
            ),
        )

    @patch(
        "pages.components."
        "survey_result_receive_panel."
        "preflight_survey_result_import"
    )
    def test_preflight_pass_is_presented_compactly(
        self,
        mock_preflight,
    ):
        report = self._report()
        mock_preflight.return_value = report

        panel = (
            SurveyResultReceivePanel()
        )

        try:
            result = panel.preflight_path(
                "demo.ydresult"
            )

            self.assertIs(
                result,
                report,
            )
            self.assertIs(
                panel.last_report,
                report,
            )
            self.assertIn(
                "可以正式导入",
                panel.overall_label.text(),
            )
            self.assertIn(
                "新增 2",
                panel.record_label.text(),
            )
            self.assertIn(
                "新增 3",
                panel.media_label.text(),
            )
            self.assertIn(
                "安全备份",
                panel.status_label.text(),
            )
        finally:
            panel.deleteLater()

    @patch(
        "pages.components."
        "survey_result_receive_panel."
        "preflight_survey_result_import"
    )
    def test_existing_only_result_is_recognized(
        self,
        mock_preflight,
    ):
        report = (
            SurveyResultImportPreflight(
                package_path=Path(
                    "same.ydresult"
                ),
                package_uid="package-1",
                result_uid="result-1",
                project_uid="project-1",
                survey_batch_uid="batch-1",
                new_assets=0,
                existing_assets=1,
                new_records=0,
                existing_records=2,
                new_inspections=0,
                existing_inspections=4,
                new_media=0,
                existing_media=3,
                issues=(),
            )
        )
        mock_preflight.return_value = report

        panel = (
            SurveyResultReceivePanel()
        )

        try:
            panel.preflight_path(
                "same.ydresult"
            )

            self.assertIn(
                "均已存在",
                panel.overall_label.text(),
            )
            self.assertIn(
                "重复成果",
                panel.status_label.text(),
            )
        finally:
            panel.deleteLater()

    def test_panel_exposes_import_action_but_disables_it_before_preflight(
        self,
    ):
        panel = (
            SurveyResultReceivePanel()
        )

        try:
            self.assertTrue(
                hasattr(
                    panel,
                    "import_button",
                )
            )
            self.assertFalse(
                panel.import_button.isEnabled()
            )
        finally:
            panel.deleteLater()


class ResultExportPageReceivePanelIntegrationTestCase(
    unittest.TestCase,
):
    def test_result_export_page_contains_receive_panel(
        self,
    ):
        page_path = (
            PROJECT_ROOT
            / "src"
            / "pages"
            / "result_export_page.py"
        )

        text = page_path.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "SurveyResultReceivePanel",
            text,
        )
        self.assertIn(
            "接收下级成果包",
            text,
        )


if __name__ == "__main__":
    unittest.main()
