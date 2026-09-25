import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class FilterStatisticsPolishContractTestCase(unittest.TestCase):
    def _read(self, relative_path: str) -> str:
        return (
            PROJECT_ROOT / relative_path
        ).read_text(encoding="utf-8")

    def test_shared_engineering_list_uses_filter_card(self):
        source = self._read(
            "src/pages/components/engineering_survey_list_page.py"
        )

        for object_name in (
            "filterCard",
            "filterTitle",
            "filterRowLabel",
            "summaryLabel",
        ):
            self.assertRegex(
                source,
                (
                    r"setObjectName\(\s*"
                    + re.escape(
                        f'\"{object_name}\"'
                    )
                    + r"\s*\)"
                ),
            )

        self.assertIn(
            "filter_action_row = QHBoxLayout()",
            source,
        )

    def test_data_query_uses_filter_card(self):
        source = self._read("src/pages/data_query_page.py")
        for fragment in (
            'setObjectName("filterCard")',
            'setObjectName("filterTitle")',
            'setObjectName("filterRowLabel")',
            "filter_action_row = QHBoxLayout()",
            'self.statistics_label.setObjectName("summaryLabel")',
        ):
            self.assertIn(fragment, source)

    def test_action_buttons_are_detached_from_last_filter_row(self):
        list_source = self._read(
            "src/pages/components/engineering_survey_list_page.py"
        )
        query_source = self._read("src/pages/data_query_page.py")

        self.assertNotIn(
            "filter_layout_2.addWidget(search_button)",
            list_source,
        )
        self.assertNotIn(
            "filter_layout_2.addWidget(reset_button)",
            list_source,
        )
        self.assertNotIn(
            "filter_row_3.addWidget(query_button)",
            query_source,
        )
        self.assertNotIn(
            "filter_row_3.addWidget(reset_button)",
            query_source,
        )

    def test_combo_box_uses_native_arrow(self):
        source = self._read("src/styles/app_theme.py")
        self.assertIn("NATIVE_COMBO_ARROW", source)
        self.assertNotIn("QComboBox::down-arrow", source)

    def test_statistics_bar_style_exists(self):
        source = self._read("src/styles/app_theme.py")
        self.assertIn("FILTER_STATISTICS_POLISH_QSS", source)
        self.assertIn("#filterCard", source)
        self.assertIn("#summaryLabel", source)


if __name__ == "__main__":
    unittest.main()
