import os
import re
import sys
import unittest
from pathlib import Path


os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from PySide6.QtWidgets import QApplication

from forms.engineering.form_2_3 import FORM_2_3
from pages.components.generic_engineering_survey_page import (
    GenericEngineeringSurveyPage,
)


class V110PreReleaseUiRegressionTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def _read(self, relative_path):
        return (
            PROJECT_ROOT
            / relative_path
        ).read_text(
            encoding="utf-8"
        )

    def test_database_queries_expose_media_count(self):
        source = self._read(
            "src/database.py"
        )

        self.assertGreaterEqual(
            source.count(
                "AS media_count"
            ),
            2,
        )

        self.assertIn(
            '"media_count": (',
            source,
        )

    def test_engineering_ledger_shows_media_column(self):
        source = self._read(
            "src/pages/engineering_asset_page.py"
        )

        self.assertIn(
            '"影像"',
            source,
        )
        self.assertIn(
            'f"有（{media_count}）"',
            source,
        )

    def test_data_query_shows_and_filters_media_state(self):
        source = self._read(
            "src/pages/data_query_page.py"
        )

        for expected in (
            "self.media_combo",
            '"有影像"',
            '"无影像"',
            '"影像"',
        ):
            self.assertIn(
                expected,
                source,
            )

        # 不依赖源码是否写成单行 record.get("media_count")
        # 或 Black/手工格式化后的多行形式。
        self.assertRegex(
            source,
            re.compile(
                r"record\.get\(\s*"
                r'["\']media_count["\']'
                r"\s*\)",
                re.MULTILINE,
            ),
        )

    def test_form_2_3_dimension_pair_uses_compact_width_role(self):
        page = GenericEngineeringSurveyPage(
            FORM_2_3
        )

        try:
            width_widget = (
                page.get_field_widget(
                    "section_width"
                )
            )
            height_widget = (
                page.get_field_widget(
                    "section_height"
                )
            )

            self.assertEqual(
                width_widget.property(
                    "uiWidthRole"
                ),
                "formPair",
            )
            self.assertEqual(
                height_widget.property(
                    "uiWidthRole"
                ),
                "formPair",
            )
        finally:
            page.deleteLater()

    def test_theme_defines_form_pair_width(self):
        source = self._read(
            "src/styles/app_theme.py"
        )

        self.assertIn(
            'uiWidthRole="formPair"',
            source,
        )
        self.assertIn(
            "min-width: 130px",
            source,
        )
        self.assertIn(
            "max-width: 130px",
            source,
        )


if __name__ == "__main__":
    unittest.main()
