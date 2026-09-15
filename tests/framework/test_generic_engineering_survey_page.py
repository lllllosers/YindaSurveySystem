import os
import sys
import unittest
from datetime import date
from pathlib import Path

os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)


# =========================================================
# 项目路径
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


# =========================================================
# 项目导入
# 必须位于 sys.path 注入之后
# =========================================================

from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
)

from forms.engineering.form_2_6 import (
    FORM_2_6,
)

from pages.components.generic_engineering_survey_page import (
    GenericEngineeringSurveyPage,
)


class GenericEngineeringSurveyPageTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(
        cls,
    ):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(
        self,
    ):
        self.page = GenericEngineeringSurveyPage(FORM_2_6)

    def tearDown(
        self,
    ):
        self.page.deleteLater()

    # =========================================================
    # 表单身份
    # =========================================================

    def test_title_comes_from_definition(
        self,
    ):
        self.assertEqual(
            self.page.title_label.text(),
            ("附表2.6 " "涵洞（暗涵）" "工程状况调查表"),
        )

    # =========================================================
    # 公共区
    # =========================================================

    def test_common_ownership_controls_exist(
        self,
    ):
        self.assertIsNotNone(self.page.department_combo)

        self.assertIsNotNone(self.page.office_combo)

        self.assertIsNotNone(self.page.canal_combo)

        self.assertIsInstance(
            self.page.business_code_edit,
            QLineEdit,
        )

        self.assertTrue(self.page.business_code_edit.isReadOnly())

    # =========================================================
    # 动态字段
    # =========================================================

    def test_all_form_2_6_fields_are_created(
        self,
    ):
        self.assertEqual(
            set(self.page.field_runtimes.keys()),
            {field.key for field in FORM_2_6.fields},
        )

        self.assertEqual(
            len(self.page.field_runtimes),
            16,
        )

    def test_dynamic_sections_are_created(
        self,
    ):
        self.assertEqual(
            len(self.page.section_groups),
            2,
        )

        titles = tuple(group.title() for group in self.page.section_groups)

        self.assertEqual(
            titles,
            (
                "二、工程基本信息",
                "三、结构与断面参数",
            ),
        )

    def test_field_widget_types_follow_definition(
        self,
    ):
        for runtime in self.page.field_runtimes.values():
            self.assertIsInstance(
                runtime.widget,
                QLineEdit,
            )

        signed_runtime = self.page.field_runtimes["channel_bottom_elevation"]

        self.assertEqual(
            signed_runtime.definition.input_type,
            "signed_decimal",
        )

    # =========================================================
    # 评价
    # =========================================================

    def test_evaluation_section_comes_from_definition(
        self,
    ):
        self.assertEqual(
            len(self.page.evaluation_section.evaluation_items),
            11,
        )

        self.assertEqual(
            self.page.evaluation_section.grade_options,
            (
                "A",
                "B",
                "C",
                "D",
            ),
        )

        self.assertEqual(
            self.page.evaluation_section.title(),
            "四、分项评价",
        )

    # =========================================================
    # 调查结论
    # =========================================================

    def test_conclusion_grades_follow_definition(
        self,
    ):
        self.assertEqual(
            tuple(self.page.overall_grade_buttons.keys()),
            (
                "A",
                "B",
                "C",
                "D",
            ),
        )

        self.assertEqual(
            self.page.conclusion_group.title(),
            "五、调查结论",
        )

    # =========================================================
    # Runtime访问
    # =========================================================

    def test_field_runtime_can_be_retrieved(
        self,
    ):
        runtime = self.page.get_field_runtime("design_flow")

        self.assertEqual(
            runtime.definition.key,
            "design_flow",
        )

        self.assertIs(
            self.page.get_field_widget("design_flow"),
            runtime.widget,
        )

    def test_unknown_field_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            KeyError,
            "不存在字段",
        ):
            self.page.get_field_runtime("missing_field")

    # =========================================================
    # 新建状态
    # =========================================================

    def test_new_page_defaults_survey_date_to_today(
        self,
    ):
        self.assertEqual(
            self.page.survey_date_edit.text(),
            date.today().isoformat(),
        )

    # =========================================================
    # record_data收集
    # =========================================================

    def test_collect_record_data(
        self,
    ):
        values = {
            "asset_name": "一号涵洞",
            "stake": "K12+350",
            "design_flow": "6.5",
            "structure_grade": "3",
            "build_date": "2010-06",
            "renovation_date": "",
            "length": "18.5",
            "increased_flow": "8.0",
            "structure_form": "箱涵",
            "main_structure_material": ("钢筋混凝土"),
            "concrete_strength": "C30",
            "cover_thickness": "40",
            "soil_cover_thickness": "2.5",
            "channel_width": "3.2",
            "channel_depth": "2.8",
            "channel_bottom_elevation": ("-1.25"),
        }

        for key, value in values.items():
            self.page.get_field_widget(key).setText(value)

        data = self.page.collect_record_data()

        self.assertEqual(
            data["asset_name"],
            "一号涵洞",
        )

        self.assertEqual(
            data["stake"],
            "CH12+350",
        )

        self.assertEqual(
            data["stake_value"],
            12350.0,
        )

        self.assertEqual(
            data["design_flow"],
            6.5,
        )

        self.assertIsNone(data["renovation_date"])

        self.assertEqual(
            data["channel_bottom_elevation"],
            -1.25,
        )

    # =========================================================
    # point位置
    # =========================================================

    def test_collect_point_position_data(
        self,
    ):
        self.page.get_field_widget("stake").setText("12350")

        position = self.page.collect_position_data()

        self.assertEqual(
            position,
            {
                "kind": "point",
                "single_stake_text": ("CH12+350"),
                "single_stake_value": (12350.0),
            },
        )

    # =========================================================
    # record_data回填
    # =========================================================

    def test_load_record_data(
        self,
    ):
        self.page.load_record_data(
            {
                "asset_name": ("回填涵洞"),
                "stake": "CH1+005",
                "design_flow": 5.5,
                "stake_value": 1005.0,
                "unknown_old_field": ("旧字段"),
            }
        )

        self.assertEqual(
            self.page.get_field_widget("asset_name").text(),
            "回填涵洞",
        )

        self.assertEqual(
            self.page.get_field_widget("stake").text(),
            "CH1+005",
        )

        self.assertEqual(
            self.page.get_field_widget("design_flow").text(),
            "5.5",
        )

    # =========================================================
    # 完整数据收集
    # =========================================================

    def test_collect_form_data(
        self,
    ):
        self.page.get_field_widget("asset_name").setText("测试涵洞")

        self.page.get_field_widget("stake").setText("CH2+100")

        first_item = FORM_2_6.evaluation_items[0]

        item_code = first_item["item_code"]

        self.page.evaluation_section.grade_buttons[item_code]["B"].setChecked(True)

        self.page.overall_grade_buttons["C"].setChecked(True)

        self.page.survey_comment_edit.setPlainText("测试意见")

        payload = self.page.collect_form_data()

        self.assertEqual(
            payload["asset_name"],
            "测试涵洞",
        )

        self.assertEqual(
            payload["position"]["single_stake_value"],
            2100.0,
        )

        self.assertEqual(
            payload["inspection_results"][0]["grade"],
            "B",
        )

        self.assertEqual(
            payload["overall_grade"],
            "C",
        )

        self.assertEqual(
            payload["survey_comment"],
            "测试意见",
        )

    # =========================================================
    # 完整数据回填
    # =========================================================

    def test_load_form_data(
        self,
    ):
        first_item = FORM_2_6.evaluation_items[0]

        item_code = first_item["item_code"]

        self.page.load_form_data(
            record_data={
                "asset_name": ("历史涵洞"),
                "stake": ("CH3+200"),
            },
            inspection_results=[
                {
                    "item_code": (item_code),
                    "grade": "D",
                }
            ],
            survey_date=("2026-09-10"),
            overall_grade="B",
            survey_comment=("历史调查意见"),
        )

        self.assertEqual(
            self.page.get_field_widget("asset_name").text(),
            "历史涵洞",
        )

        self.assertTrue(
            self.page.evaluation_section.grade_buttons[item_code]["D"].isChecked()
        )

        self.assertTrue(self.page.overall_grade_buttons["B"].isChecked())

        self.assertEqual(
            self.page.survey_date_edit.text(),
            "2026-09-10",
        )

        self.assertEqual(
            self.page.survey_comment_edit.toPlainText(),
            "历史调查意见",
        )

    # =========================================================
    # prepare_new
    # =========================================================

    def test_prepare_new_clears_form_and_defaults_date(
        self,
    ):
        self.page.get_field_widget("asset_name").setText("待清空")

        self.page.overall_grade_buttons["A"].setChecked(True)

        self.page.survey_comment_edit.setPlainText("待清空意见")

        self.page.prepare_new()

        self.assertTrue(self.page.get_field_runtime("asset_name").is_blank())

        self.assertIsNone(self.page.get_overall_grade())

        self.assertEqual(
            self.page.survey_comment_edit.toPlainText(),
            "",
        )

        self.assertEqual(
            self.page.survey_date_edit.text(),
            date.today().isoformat(),
        )

    def test_prepare_new_can_preserve_survey_date(
        self,
    ):
        self.page.prepare_new(survey_date=("2026-09-01"))

        self.assertEqual(
            self.page.survey_date_edit.text(),
            "2026-09-01",
        )

    # =========================================================
    # 完成调查校验
    # =========================================================

    def test_empty_page_fails_completion_validation(
        self,
    ):
        errors = self.page.validate_for_completion()

        self.assertIn(
            "名称不能为空。",
            errors,
        )

        self.assertIn(
            "请选择工程状况类别。",
            errors,
        )

        self.assertIn(
            "请填写调查意见与建议。",
            errors,
        )

    def test_invalid_month_is_reported_by_completion_validation(
        self,
    ):
        self.page.get_field_widget("build_date").setText("2026-13")

        errors = self.page.validate_for_completion()

        self.assertTrue(any("YYYY-MM" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
