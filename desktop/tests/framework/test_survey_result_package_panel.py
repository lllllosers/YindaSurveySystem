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

from pages.components.survey_result_package_panel import (
    SurveyResultPackagePanel,
)
from services.survey_scope import SurveyScope


class SurveyResultPackagePanelTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def _context(self):
        return {
            "project_id": 1,
            "batch_id": 2,
        }

    def _scope(self):
        return SurveyScope(
            project_id=1,
            survey_batch_id=2,
            record_statuses=(
                "completed",
            ),
        )

    @patch(
        "pages.components."
        "survey_result_package_panel."
        "database.get_connection"
    )
    @patch(
        "pages.components."
        "survey_result_package_panel."
        "load_scope_records"
    )
    def test_refresh_scope_uses_completed_scope_records(
        self,
        mock_load,
        mock_connection,
    ):
        mock_load.return_value = [
            {
                "survey_record_id": 11,
            },
            {
                "survey_record_id": 12,
            },
        ]

        connection = (
            mock_connection.return_value
            .__enter__.return_value
        )

        project_result = MagicMock()
        project_result.fetchone.return_value = {
            "project_uid": "project-u",
            "name": "项目",
        }

        batch_result = MagicMock()
        batch_result.fetchone.return_value = {
            "survey_batch_uid": "batch-u",
            "batch_name": "2026批次",
        }

        connection.execute.side_effect = [
            project_result,
            batch_result,
        ]

        panel = SurveyResultPackagePanel(
            context_provider=self._context,
            scope_provider=self._scope,
        )

        try:
            record_ids = (
                panel.refresh_scope_summary()
            )

            self.assertEqual(
                record_ids,
                (
                    11,
                    12,
                ),
            )
            self.assertIn(
                "2 条",
                panel.scope_summary_label.text(),
            )
            self.assertEqual(
                panel.result_name_edit.text(),
                "2026批次调查成果",
            )
            self.assertTrue(
                panel.export_button.isEnabled()
            )

        finally:
            panel.deleteLater()

    @patch(
        "pages.components."
        "survey_result_package_panel."
        "database.get_connection"
    )
    @patch(
        "pages.components."
        "survey_result_package_panel."
        "load_scope_records",
        return_value=[],
    )
    def test_empty_scope_disables_package_export(
        self,
        mock_load,
        mock_connection,
    ):
        connection = (
            mock_connection.return_value
            .__enter__.return_value
        )

        project_result = MagicMock()
        project_result.fetchone.return_value = {
            "project_uid": "project-u",
            "name": "项目",
        }

        batch_result = MagicMock()
        batch_result.fetchone.return_value = {
            "survey_batch_uid": "batch-u",
            "batch_name": "批次",
        }

        connection.execute.side_effect = [
            project_result,
            batch_result,
        ]

        panel = SurveyResultPackagePanel(
            context_provider=self._context,
            scope_provider=self._scope,
        )

        try:
            panel.refresh_scope_summary()

            self.assertFalse(
                panel.export_button.isEnabled()
            )
            self.assertIn(
                "0 条",
                panel.scope_summary_label.text(),
            )

        finally:
            panel.deleteLater()


if __name__ == "__main__":
    unittest.main()
