import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class FilterLayoutRefineContractTestCase(unittest.TestCase):
    def _read(self, relative_path: str) -> str:
        return (
            PROJECT_ROOT / relative_path
        ).read_text(encoding="utf-8")

    def test_engineering_list_uses_four_character_group_labels(self):
        source = self._read(
            "src/pages/components/engineering_survey_list_page.py"
        )
        self.assertIn('"范围检索"', source)
        self.assertIn('"状态评价"', source)
        self.assertNotIn('"范围与关键词"', source)
        self.assertNotIn('"状态与评价"', source)

    def test_engineering_list_filter_controls_are_consistent(self):
        source = self._read(
            "src/pages/components/engineering_survey_list_page.py"
        )
        self.assertIn(
            'self.keyword_edit.setProperty("uiWidthRole", "filter")',
            source,
        )
        self.assertIn(
            'self.department_filter.setProperty("uiWidthRole", "filter")',
            source,
        )
        self.assertIn(
            'self.office_filter.setProperty("uiWidthRole", "filter")',
            source,
        )
        self.assertIn(
            'self.canal_filter.setProperty("uiWidthRole", "filter")',
            source,
        )
        self.assertIn(
            "filter_layout_1.addStretch()",
            source,
        )
        self.assertIn(
            "filter_layout_2.addStretch()",
            source,
        )

    def test_data_query_filter_controls_are_consistent_and_left_packed(self):
        source = self._read(
            "src/pages/data_query_page.py"
        )

        for target in (
            "self.batch_combo",
            "self.form_combo",
            "self.keyword_edit",
            "self.department_combo",
            "self.office_combo",
            "self.canal_combo",
            "self.status_combo",
            "self.grade_combo",
        ):
            self.assertIn(
                f'{target}.setProperty("uiWidthRole", "filter")',
                source,
            )

        for row_name in (
            "filter_row_1",
            "filter_row_2",
            "filter_row_3",
        ):
            self.assertIn(
                f"{row_name}.addStretch()",
                source,
            )


if __name__ == "__main__":
    unittest.main()
