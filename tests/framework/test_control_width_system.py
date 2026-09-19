import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ControlWidthSystemContractTestCase(unittest.TestCase):
    def _read(self, relative_path: str) -> str:
        return (
            PROJECT_ROOT / relative_path
        ).read_text(encoding="utf-8")

    def test_theme_defines_consistent_width_roles(self):
        source = self._read("src/styles/app_theme.py")

        self.assertIn("CONTROL_WIDTH_SYSTEM_QSS", source)
        self.assertIn('uiWidthRole="filter"', source)
        self.assertIn('uiWidthRole="form"', source)
        self.assertIn("min-width: 200px", source)
        self.assertIn("max-width: 200px", source)
        self.assertIn("min-width: 280px", source)
        self.assertIn("max-width: 280px", source)

    def test_filter_pages_use_shared_filter_width_role(self):
        for relative_path in (
            "src/pages/data_query_page.py",
            "src/pages/components/engineering_survey_list_page.py",
        ):
            source = self._read(relative_path)
            self.assertIn(
                'setProperty("uiWidthRole", "filter")',
                source,
            )
            self.assertNotIn(".setMinimumWidth(", source)
            self.assertNotIn(".setMaximumWidth(", source)

    def test_dynamic_engineering_fields_use_form_width_role(self):
        source = self._read(
            "src/pages/components/engineering_field_runtime.py"
        )
        self.assertIn(
            'widget.setProperty("uiWidthRole", "form")',
            source,
        )

    def test_generic_engineering_form_ownership_fields_are_consistent(self):
        source = self._read(
            "src/pages/components/generic_engineering_survey_page.py"
        )

        for target in (
            "self.department_combo",
            "self.office_combo",
            "self.canal_combo",
            "self.task_scope_combo",
            "self.business_code_edit",
        ):
            self.assertIn(
                f'{target}.setProperty("uiWidthRole", "form")',
                source,
            )

    def test_workflow_pages_use_standard_form_width_role(self):
        for relative_path in (
            "src/pages/survey_task_page.py",
            "src/pages/result_export_page.py",
            "src/pages/components/survey_result_package_panel.py",
        ):
            source = self._read(relative_path)
            self.assertIn(
                'setProperty("uiWidthRole", "form")',
                source,
            )


if __name__ == "__main__":
    unittest.main()
