import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class SharedEngineeringUiContractTestCase(unittest.TestCase):
    def _read(self, relative_path: str) -> str:
        return (
            PROJECT_ROOT / relative_path
        ).read_text(encoding="utf-8")

    def test_shared_list_page_has_consistent_action_roles(self):
        source = self._read(
            "src/pages/components/engineering_survey_list_page.py"
        )

        self.assertIn(
            'new_button.setProperty("uiRole", "primary")',
            source,
        )
        self.assertIn(
            'delete_button.setProperty("uiRole", "danger")',
            source,
        )
        self.assertIn(
            'search_button.setProperty("uiRole", "primary")',
            source,
        )
        self.assertIn(
            '"导出正式原表"',
            source,
        )

    def test_shared_list_page_uses_common_visual_ids(self):
        source = self._read(
            "src/pages/components/engineering_survey_list_page.py"
        )

        for fragment in (
            'title.setObjectName("sectionPageTitle")',
            'description.setObjectName("pageDescription")',
            'self.count_label.setObjectName("summaryLabel")',
            'self.table.setObjectName("dataTable")',
        ):
            self.assertIn(fragment, source)

    def test_shared_survey_page_has_consistent_footer_roles(self):
        source = self._read(
            "src/pages/components/generic_engineering_survey_page.py"
        )

        self.assertIn(
            'self.back_button.setProperty("uiRole", "secondary")',
            source,
        )
        self.assertIn(
            'self.save_button.setProperty("uiRole", "secondary")',
            source,
        )
        self.assertIn(
            'self.complete_button.setProperty("uiRole", "primary")',
            source,
        )
        self.assertIn(
            'self.title_label.setObjectName("sectionPageTitle")',
            source,
        )
        self.assertIn(
            'self.description_label.setObjectName("pageDescription")',
            source,
        )

    def test_theme_contains_shared_engineering_ui_marker(self):
        source = self._read(
            "src/styles/app_theme.py"
        )

        self.assertIn(
            "SHARED_ENGINEERING_UI_QSS",
            source,
        )
        self.assertIn(
            'QPushButton[uiRole="primary"]',
            source,
        )
        self.assertIn(
            'QPushButton[uiRole="danger"]',
            source,
        )


if __name__ == "__main__":
    unittest.main()
