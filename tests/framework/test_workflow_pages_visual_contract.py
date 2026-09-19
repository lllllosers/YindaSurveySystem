import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class WorkflowPagesVisualContractTestCase(unittest.TestCase):
    def _read(self, relative_path: str) -> str:
        return (
            PROJECT_ROOT / relative_path
        ).read_text(encoding="utf-8")

    def test_theme_has_workflow_visual_contract(self):
        source = self._read("src/styles/app_theme.py")

        self.assertIn("WORKFLOW_UI_POLISH_QSS", source)
        self.assertIn('workflowCard="true"', source)
        self.assertIn("#workflowLead", source)
        self.assertIn("#workflowStatus", source)
        self.assertIn("#workflowSummary", source)

    def test_task_distribution_has_visual_hierarchy(self):
        source = self._read("src/pages/survey_task_page.py")

        self.assertIn('setProperty("workflowCard", True)', source)
        self.assertIn('setObjectName("workflowLead")', source)
        self.assertIn(
            'self.export_button.setProperty("uiRole", "primary")',
            source,
        )
        self.assertIn(
            'self.inspect_button.setProperty("uiRole", "secondary")',
            source,
        )

    def test_task_receive_actions_are_split_left_and_right(self):
        source = self._read(
            "src/pages/components/survey_task_receive_panel.py"
        )

        # Keep the existing business-facing wording. The important contract is
        # that the main button no longer exposes the .ydtask extension.
        self.assertIn('"选择并接收任务包"', source)
        self.assertNotIn('"接收 .ydtask"', source)

        start = source.index("action_row = QHBoxLayout()")
        end = source.index("layout.addLayout(", start)
        block = source[start:end]

        positions = [
            block.index("addWidget(self.refresh_button)"),
            block.index("addStretch()"),
            block.index("addWidget(self.receive_button)"),
        ]

        self.assertEqual(positions, sorted(positions))
        self.assertIn(
            'self.receive_button.setProperty("uiRole", "primary")',
            source,
        )

    def test_result_submit_uses_cards_and_primary_actions(self):
        export_page = self._read("src/pages/result_export_page.py")
        package_panel = self._read(
            "src/pages/components/survey_result_package_panel.py"
        )

        self.assertIn(
            'setProperty("workflowCard", True)',
            export_page,
        )
        self.assertIn(
            'self.export_button.setProperty("uiRole", "primary")',
            export_page,
        )
        self.assertIn(
            '"生成调查成果包"',
            package_panel,
        )
        self.assertIn(
            'self.export_button.setProperty("uiRole", "primary")',
            package_panel,
        )

    def test_result_receive_uses_business_wording_and_action_split(self):
        source = self._read(
            "src/pages/components/survey_result_receive_panel.py"
        )

        self.assertIn('"选择成果包并预检"', source)
        self.assertNotIn('"选择 .ydresult 并预检"', source)

        start = source.index("action_row = QHBoxLayout()")
        end = source.index("root.addLayout(", start)
        block = source[start:end]

        positions = [
            block.index("addWidget(self.preflight_button)"),
            block.index("addStretch()"),
            block.index("addWidget(self.import_button)"),
        ]

        self.assertEqual(positions, sorted(positions))
        self.assertIn(
            'self.import_button.setProperty("uiRole", "primary")',
            source,
        )
        self.assertIn(
            'self.details_edit.setObjectName("workflowDetails")',
            source,
        )


if __name__ == "__main__":
    unittest.main()
