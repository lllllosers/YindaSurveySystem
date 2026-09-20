import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

SRC_DIR = (
    PROJECT_ROOT
    / "src"
)

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from PySide6.QtWidgets import QApplication

from pages.components.survey_result_package_panel import (
    SurveyResultPackagePanel,
)


class Stage45BResultSubmissionUiTestCase(
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
        "survey_result_package_panel."
        "preview_current_department_aggregate"
    )
    @patch.object(
        SurveyResultPackagePanel,
        "_current_local_identity",
    )
    def test_department_workspace_uses_auto_aggregate_preview(
        self,
        mock_identity,
        mock_preview,
    ):
        mock_identity.return_value = {
            "project_id": 1,
            "batch_id": 2,
            "batch_name": "2026批次",
        }

        mock_preview.return_value = (
            SimpleNamespace(
                parent_task_uid="T1",
                survey_record_ids=(
                    11,
                    12,
                ),
                record_count=2,
                source_task_count=2,
                source_office_count=2,
                management_scope_count=3,
            )
        )

        panel = SurveyResultPackagePanel(
            context_provider=lambda: {
                "project_id": 1,
                "batch_id": 2,
            },
            scope_provider=lambda: (_ for _ in ()).throw(
                AssertionError(
                    "处级汇总不应读取普通筛选 scope"
                )
            ),
            workspace_provider=lambda: {
                "task_uid": "T1",
                "target_unit_type": "department",
            },
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

            self.assertEqual(
                panel.result_name_edit.text(),
                "2026批次处级汇总成果",
            )

            self.assertEqual(
                panel.export_button.text(),
                "生成处级汇总成果包",
            )

            self.assertIn(
                "2 条记录",
                panel.scope_summary_label.text(),
            )

            self.assertIn(
                "来源子任务 2 个",
                panel.scope_summary_label.text(),
            )

            self.assertIn(
                "上方成果范围筛选不会改变",
                panel.scope_summary_label.text(),
            )

            self.assertTrue(
                panel.export_button.isEnabled()
            )

        finally:
            panel.deleteLater()

    def test_source_contract_sets_submission_task_uid(
        self,
    ):
        source = (
            SRC_DIR
            / "pages"
            / "components"
            / "survey_result_package_panel.py"
        ).read_text(
            encoding="utf-8"
        )

        required = (
            "preview_current_department_aggregate",
            "submission_task_uid=(",
            "preview.parent_task_uid",
            '== "water_office"',
            "workspace_provider",
        )

        for token in required:
            self.assertIn(
                token,
                source,
            )


if __name__ == "__main__":
    unittest.main()
