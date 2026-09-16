import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from PySide6.QtWidgets import (
    QApplication,
)

from forms.engineering.form_2_1 import (
    FORM_2_1,
)

from forms.engineering.form_2_2 import (
    FORM_2_2,
)

from forms.engineering.form_2_3 import (
    FORM_2_3,
)

from forms.engineering.form_2_4 import (
    FORM_2_4,
)

from pages.components.generic_engineering_survey_page import (
    GenericEngineeringSurveyPage,
)


class Forms21To24GenericPageTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(
        cls,
    ):
        cls.app = QApplication.instance() or QApplication([])

    def test_all_definitions_can_build_generic_page(
        self,
    ):
        for definition in (
            FORM_2_1,
            FORM_2_2,
            FORM_2_3,
            FORM_2_4,
        ):
            with self.subTest(form_code=definition.form_code):
                page = GenericEngineeringSurveyPage(definition)

                try:
                    self.assertIs(
                        page.definition,
                        definition,
                    )

                    self.assertEqual(
                        set(page.field_runtimes.keys()),
                        {field.key for field in definition.fields},
                    )

                finally:
                    page.deleteLater()

    def test_form_2_1_nonstandard_asset_name_and_range(
        self,
    ):
        page = GenericEngineeringSurveyPage(FORM_2_1)

        try:
            page.get_field_widget("channel_name").setText("测试渠道渠段")

            page.get_field_widget("start_stake").setText("CH10+000")

            page.get_field_widget("end_stake").setText("CH11+250")

            record_data = page.collect_record_data()

            position_data = page.collect_position_data()

            self.assertEqual(
                record_data["channel_name"],
                "测试渠道渠段",
            )

            self.assertEqual(
                position_data,
                {
                    "kind": "range",
                    "start_stake_text": ("CH10+000"),
                    "start_stake_value": (10000.0),
                    "end_stake_text": ("CH11+250"),
                    "end_stake_value": (11250.0),
                },
            )

        finally:
            page.deleteLater()

    def test_form_2_2_integer_field_runtime(
        self,
    ):
        page = GenericEngineeringSurveyPage(FORM_2_2)

        try:
            page.get_field_widget("opening_count").setText("3")

            data = page.collect_record_data()

            self.assertEqual(
                data["opening_count"],
                3,
            )

        finally:
            page.deleteLater()

    def test_form_2_3_composite_fields_are_available(
        self,
    ):
        page = GenericEngineeringSurveyPage(FORM_2_3)

        try:
            page.get_field_widget("section_width").setText("3.2")

            page.get_field_widget("section_height").setText("2.4")

            data = page.collect_record_data()

            self.assertEqual(
                data["section_width"],
                3.2,
            )

            self.assertEqual(
                data["section_height"],
                2.4,
            )

        finally:
            page.deleteLater()

    def test_form_2_4_signed_elevation_runtime(
        self,
    ):
        page = GenericEngineeringSurveyPage(FORM_2_4)

        try:
            page.get_field_widget("channel_bottom_elevation").setText("-12.5")

            data = page.collect_record_data()

            self.assertEqual(
                data["channel_bottom_elevation"],
                -12.5,
            )

        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
