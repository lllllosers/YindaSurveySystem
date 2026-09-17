import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


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
    QAbstractScrollArea,
    QApplication,
    QScrollArea,
)

from forms.engineering.registry import (
    get_engineering_asset_type_display_name,
    get_engineering_form_definitions,
)
from pages.components.engineering_survey_list_page import (
    EngineeringSurveyListPage,
)
from pages.components.generic_engineering_survey_page import (
    GenericEngineeringSurveyPage,
)
from pages.survey_page import (
    SurveyPage,
)


class EngineeringUsabilityFeedbackTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(
        cls,
    ):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def test_engineering_home_uses_independent_scroll_area(
        self,
    ):
        with patch.object(
            EngineeringSurveyListPage,
            "load_data",
            return_value=None,
        ):
            page = SurveyPage()

        try:
            self.assertIsInstance(
                page.engineering_home_scroll_area,
                QScrollArea,
            )
            self.assertTrue(
                page.engineering_home_scroll_area
                .widgetResizable()
            )
            self.assertEqual(
                page.engineering_home_scroll_area
                .sizeAdjustPolicy(),
                QAbstractScrollArea
                .SizeAdjustPolicy
                .AdjustIgnored,
            )
            self.assertEqual(
                len(
                    page.engineering_form_buttons
                ),
                len(
                    get_engineering_form_definitions()
                ),
            )
        finally:
            page.deleteLater()

    def test_generic_survey_page_can_reset_scroll_to_top(
        self,
    ):
        definition = (
            get_engineering_form_definitions()[0]
        )

        page = GenericEngineeringSurveyPage(
            definition
        )

        try:
            bar = (
                page.scroll_area
                .verticalScrollBar()
            )

            bar.setValue(
                bar.maximum()
            )

            page.reset_view_to_top(
                focus_first=False
            )

            self.assertEqual(
                bar.value(),
                bar.minimum(),
            )
        finally:
            page.deleteLater()

    def test_all_registered_asset_types_have_chinese_display_name(
        self,
    ):
        for definition in (
            get_engineering_form_definitions()
        ):
            with self.subTest(
                asset_type=definition.asset_type,
            ):
                display_name = (
                    get_engineering_asset_type_display_name(
                        definition.asset_type
                    )
                )

                self.assertTrue(
                    display_name
                )
                self.assertNotEqual(
                    display_name,
                    definition.asset_type,
                )
                self.assertNotIn(
                    "调查表",
                    display_name,
                )

    def test_unknown_asset_type_falls_back_without_crashing(
        self,
    ):
        self.assertEqual(
            get_engineering_asset_type_display_name(
                "legacy_unknown_type"
            ),
            "legacy_unknown_type",
        )


if __name__ == "__main__":
    unittest.main()
