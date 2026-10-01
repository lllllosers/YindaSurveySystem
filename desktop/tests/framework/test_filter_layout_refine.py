import re
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

        for target in (
            "self.keyword_edit",
            "self.department_filter",
            "self.office_filter",
            "self.canal_filter",
        ):
            self.assertRegex(
                source,
                (
                    rf"{re.escape(target)}"
                    r"\.setProperty\(\s*"
                    r"\"uiWidthRole\"\s*,\s*"
                    r"\"filter\"\s*,?\s*\)"
                ),
            )

        # V1.0.2: 工程调查列表由原来的两条横向 HBox
        # 改为响应式 Grid，避免默认窗口宽度下控件互相挤压。
        self.assertRegex(
            source,
            (
                r"range_grid\.setObjectName\(\s*"
                r"\"filterRangeGrid\"\s*\)"
            ),
        )
        self.assertRegex(
            source,
            (
                r"status_grid\.setObjectName\(\s*"
                r"\"filterStatusGrid\"\s*\)"
            ),
        )
        self.assertIn(
            "range_grid.setColumnStretch(",
            source,
        )
        self.assertIn(
            "status_grid.setColumnStretch(",
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
