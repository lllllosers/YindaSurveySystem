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


from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
)

from pages.components.survey_result_receive_panel import (
    SurveyResultReceivePanel,
)
from services.survey_result_import_preflight import (
    SurveyResultImportPreflight,
    SurveyResultPreflightIssue,
)


class SurveyResultReceiveImportUiTestCase(
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
        can_import=True,
        has_new=True,
    ):
        issues = ()

        if not can_import:
            issues = (
                SurveyResultPreflightIssue(
                    severity="error",
                    code="DEMO_ERROR",
                    message="测试冲突",
                ),
            )

        return SurveyResultImportPreflight(
            package_path=Path(
                "demo.ydresult"
            ),
            package_uid="package-1",
            result_uid="result-1",
            project_uid="project-1",
            survey_batch_uid="batch-1",
            new_assets=(
                1
                if has_new
                else 0
            ),
            existing_assets=(
                0
                if has_new
                else 1
            ),
            new_records=(
                2
                if has_new
                else 0
            ),
            existing_records=(
                0
                if has_new
                else 2
            ),
            new_inspections=(
                3
                if has_new
                else 0
            ),
            existing_inspections=(
                0
                if has_new
                else 3
            ),
            new_media=(
                4
                if has_new
                else 0
            ),
            existing_media=(
                0
                if has_new
                else 4
            ),
            issues=issues,
        )

    def test_import_button_disabled_before_preflight(
        self,
    ):
        panel = (
            SurveyResultReceivePanel()
        )

        try:
            self.assertFalse(
                panel.import_button.isEnabled()
            )
        finally:
            panel.deleteLater()

    @patch(
        "pages.components."
        "survey_result_receive_panel."
        "preflight_survey_result_import"
    )
    def test_successful_preflight_enables_import(
        self,
        mock_preflight,
    ):
        mock_preflight.return_value = (
            self._report()
        )

        panel = (
            SurveyResultReceivePanel()
        )

        try:
            panel.preflight_path(
                "demo.ydresult"
            )

            self.assertTrue(
                panel.import_button.isEnabled()
            )
        finally:
            panel.deleteLater()

    @patch(
        "pages.components."
        "survey_result_receive_panel."
        "preflight_survey_result_import"
    )
    def test_existing_only_result_keeps_import_disabled(
        self,
        mock_preflight,
    ):
        mock_preflight.return_value = (
            self._report(
                has_new=False,
            )
        )

        panel = (
            SurveyResultReceivePanel()
        )

        try:
            panel.preflight_path(
                "demo.ydresult"
            )

            self.assertFalse(
                panel.import_button.isEnabled()
            )
        finally:
            panel.deleteLater()

    @patch(
        "pages.components."
        "survey_result_receive_panel."
        "preflight_survey_result_import"
    )
    def test_conflict_keeps_import_disabled(
        self,
        mock_preflight,
    ):
        mock_preflight.return_value = (
            self._report(
                can_import=False,
            )
        )

        panel = (
            SurveyResultReceivePanel()
        )

        try:
            panel.preflight_path(
                "demo.ydresult"
            )

            self.assertFalse(
                panel.import_button.isEnabled()
            )
        finally:
            panel.deleteLater()

    @patch(
        "pages.components."
        "survey_result_receive_panel."
        "QMessageBox.question",
        return_value=(
            QMessageBox.StandardButton.Yes
        ),
    )
    @patch(
        "pages.components."
        "survey_result_receive_panel."
        "preflight_survey_result_import"
    )
    def test_confirmed_import_starts_worker(
        self,
        mock_preflight,
        mock_question,
    ):
        mock_preflight.return_value = (
            self._report()
        )

        panel = (
            SurveyResultReceivePanel()
        )

        try:
            panel.preflight_path(
                "demo.ydresult"
            )

            panel._begin_import = (
                MagicMock()
            )

            panel.import_current_package()

            panel._begin_import.assert_called_once_with(
                Path(
                    "demo.ydresult"
                )
            )

            mock_question.assert_called_once()
        finally:
            panel.deleteLater()

    def test_result_export_page_refreshes_package_scope_after_import(
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
            (
                "self.result_receive_panel."
                "result_imported.connect"
            ),
            text,
        )


if __name__ == "__main__":
    unittest.main()
