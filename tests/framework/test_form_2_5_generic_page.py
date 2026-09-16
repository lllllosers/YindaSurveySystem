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

from forms.engineering.form_2_5 import (
    FORM_2_5,
)

from pages.components.generic_engineering_survey_page import (
    GenericEngineeringSurveyPage,
)


class Form25GenericPageTestCase(
    unittest.TestCase,
):
    """
    附表2.5作为真实 range golden sample
    接入 GenericEngineeringSurveyPage 的测试。

    此阶段只验证 definition 驱动能力，
    暂不切换生产入口。
    """

    @classmethod
    def setUpClass(
        cls,
    ):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(
        self,
    ):
        self.page = GenericEngineeringSurveyPage(FORM_2_5)

    def tearDown(
        self,
    ):
        self.page.deleteLater()

    def test_page_uses_form_2_5_definition(
        self,
    ):
        self.assertIs(
            self.page.definition,
            FORM_2_5,
        )

        self.assertEqual(
            self.page.title_label.text(),
            (f"{FORM_2_5.display_name}" " - 新增"),
        )

        self.assertEqual(
            set(self.page.field_runtimes.keys()),
            {field.key for field in FORM_2_5.fields},
        )

    def test_range_position_is_collected(
        self,
    ):
        self.page.get_field_widget("start_stake").setText("CH20+000")

        self.page.get_field_widget("end_stake").setText("CH21+200")

        position = self.page.collect_position_data()

        self.assertEqual(
            position,
            {
                "kind": "range",
                "start_stake_text": "CH20+000",
                "start_stake_value": 20000.0,
                "end_stake_text": "CH21+200",
                "end_stake_value": 21200.0,
            },
        )

    def test_record_data_matches_expected_types(
        self,
    ):
        values = {
            "asset_name": "测试隧洞",
            "start_stake": "CH20+000",
            "end_stake": "CH21+200",
            "design_flow": "8.5",
            "structure_grade": "3级",
            "build_date": "2010-06",
            "renovation_date": "",
            "length": "1200",
            "increased_flow": "10",
            "lining_form": "钢筋混凝土衬砌",
            "lining_thickness": "0.30",
            "concrete_strength": "C30",
            "inlet_outlet_bottom_elevation": ("1680.25"),
            "longitudinal_slope": "1.5",
            "section_form": "城门洞型",
            "section_width": "3.0",
            "section_height": "3.5",
            "cover_thickness": "0.05",
        }

        for key, value in values.items():
            self.page.get_field_widget(key).setText(value)

        data = self.page.collect_record_data()

        self.assertEqual(
            data["asset_name"],
            "测试隧洞",
        )

        self.assertEqual(
            data["start_stake"],
            "CH20+000",
        )

        self.assertEqual(
            data["start_stake_value"],
            20000.0,
        )

        self.assertEqual(
            data["end_stake"],
            "CH21+200",
        )

        self.assertEqual(
            data["end_stake_value"],
            21200.0,
        )

        self.assertEqual(
            data["design_flow"],
            8.5,
        )

        self.assertEqual(
            data["length"],
            1200.0,
        )

        self.assertEqual(
            data["inlet_outlet_bottom_elevation"],
            "1680.25",
        )

        self.assertIsNone(data["renovation_date"])

    def test_complete_form_passes_validation(
        self,
    ):
        for field in FORM_2_5.fields:
            widget = self.page.get_field_widget(field.key)

            if field.key == "asset_name":
                value = "完整测试隧洞"

            elif field.key == "start_stake":
                value = "CH20+000"

            elif field.key == "end_stake":
                value = "CH21+200"

            elif field.key == "renovation_date":
                value = ""

            elif field.input_type == "text":
                value = "测试"

            elif field.input_type in (
                "decimal",
                "signed_decimal",
            ):
                value = "1"

            elif field.input_type == "integer":
                value = "1"

            elif field.input_type == "month":
                value = "2026-01"

            else:
                raise AssertionError("测试未覆盖字段类型：" f"{field.input_type}")

            widget.setText(value)

        for item in FORM_2_5.evaluation_items:
            item_code = item["item_code"]

            self.page.evaluation_section.grade_buttons[item_code]["A"].setChecked(True)

        self.page.set_overall_grade("A")

        self.page.survey_date_edit.setText("2026-09-16")

        self.page.survey_comment_edit.setPlainText("完整测试调查意见。")

        errors = self.page.validate_for_completion()

        self.assertEqual(
            errors,
            [],
        )

    def test_range_end_cannot_precede_start(
        self,
    ):
        self.page.get_field_widget("start_stake").setText("CH21+200")

        self.page.get_field_widget("end_stake").setText("CH20+000")

        errors = self.page.validate_for_completion()

        self.assertTrue(any("终止桩号不能小于起始桩号" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
