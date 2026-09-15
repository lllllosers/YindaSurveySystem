import os
import sys
import unittest
from datetime import date
from pathlib import Path

from unittest.mock import patch

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
    QMessageBox,
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
            (f"{FORM_2_6.display_name}" " - 新增"),
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

    # =========================================================
    # 运行时上下文 / 业务编号
    # =========================================================

    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_engineering_business_codes",
        return_value=[],
    )
    def test_business_code_uses_definition_type_code(
        self,
        mock_codes,
    ):
        self.page.current_context = {
            "project_id": 1,
            "batch_id": 2,
        }

        self.page.department_combo.addItem(
            "测试处",
            {
                "id": 10,
                "business_code": "1",
            },
        )

        self.page.office_combo.addItem(
            "测试所",
            {
                "id": 20,
                "business_code": "01",
            },
        )

        self.page.canal_combo.addItem(
            "测试干渠",
            {
                "id": 30,
                "canal_level": "01",
            },
        )

        self.page.update_business_code()

        self.assertEqual(
            self.page.business_code_edit.text(),
            "1-01-01-06-001",
        )

        mock_codes.assert_called()

    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_engineering_business_codes",
        return_value=[],
    )
    def test_prepare_new_preserves_ownership(
        self,
        mock_codes,
    ):
        self.page.current_context = {
            "project_id": 1,
            "batch_id": 2,
        }

        self.page.department_combo.addItem(
            "测试处",
            {
                "id": 10,
                "business_code": "1",
            },
        )

        self.page.office_combo.addItem(
            "测试所",
            {
                "id": 20,
                "business_code": "01",
            },
        )

        self.page.canal_combo.addItem(
            "测试干渠",
            {
                "id": 30,
                "canal_level": "01",
            },
        )

        self.page.editing_record_id = 99
        self.page.editing_record_status = "completed"

        self.page.prepare_new(survey_date="2026-09-15")

        self.assertIsNone(self.page.editing_record_id)

        self.assertIsNone(self.page.editing_record_status)

        self.assertEqual(
            self.page.department_combo.currentData()["id"],
            10,
        )

        self.assertEqual(
            self.page.office_combo.currentData()["id"],
            20,
        )

        self.assertEqual(
            self.page.canal_combo.currentData()["id"],
            30,
        )

        self.assertEqual(
            self.page.business_code_edit.text(),
            "1-01-01-06-001",
        )

        self.assertFalse(self.page.is_dirty)

    def test_user_field_edit_marks_page_dirty(
        self,
    ):
        self.assertFalse(self.page.is_dirty)

        runtime = self.page.get_field_runtime("asset_name")

        runtime.widget.textEdited.emit("用户修改")

        self.assertTrue(self.page.is_dirty)

    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_engineering_business_codes",
        return_value=[],
    )
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_canal_units_for_organization"
    )
    @patch("pages.components." "generic_engineering_survey_page." "get_water_offices")
    @patch("pages.components." "generic_engineering_survey_page." "get_departments")
    def test_ownership_cascade_loads_business_code(
        self,
        mock_departments,
        mock_offices,
        mock_canals,
        mock_codes,
    ):
        mock_departments.return_value = [
            {
                "id": 1,
                "name": "测试基层处",
                "business_code": "1",
                "status": "active",
            }
        ]

        mock_offices.return_value = [
            {
                "id": 2,
                "name": "测试水管所",
                "business_code": "01",
                "status": "active",
            }
        ]

        mock_canals.return_value = [
            {
                "id": 3,
                "name": "测试干渠",
                "canal_level": "01",
            }
        ]

        self.page.current_context = {
            "project_id": 1,
            "batch_id": 2,
        }

        self.page.load_departments()

        self.assertEqual(
            self.page.department_combo.count(),
            1,
        )

        self.assertEqual(
            self.page.office_combo.count(),
            1,
        )

        self.assertEqual(
            self.page.canal_combo.count(),
            1,
        )

        self.assertEqual(
            self.page.business_code_edit.text(),
            "1-01-01-06-001",
        )

    def _seed_ownership(
        self,
    ):
        combos = [
            (
                self.page.department_combo,
                "测试基层处",
                {
                    "id": 10,
                    "business_code": "1",
                },
            ),
            (
                self.page.office_combo,
                "测试水管所",
                {
                    "id": 20,
                    "business_code": "01",
                },
            ),
            (
                self.page.canal_combo,
                "测试干渠",
                {
                    "id": 30,
                    "canal_level": "01",
                },
            ),
        ]

        for combo, text, data in combos:
            combo.blockSignals(True)

            combo.clear()

            combo.addItem(
                text,
                data,
            )

            combo.blockSignals(False)

        self.page.business_code_edit.setText("1-01-01-06-001")

    # =========================================================
    # 草稿生命周期
    # =========================================================

    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "create_engineering_record"
    )
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_current_form_version"
    )
    @patch("pages.components." "generic_engineering_survey_page." "get_current_context")
    def test_first_save_creates_draft_and_locks_ownership(
        self,
        mock_context,
        mock_form_version,
        mock_create,
    ):
        mock_context.return_value = {
            "project_id": 1,
            "batch_id": 2,
        }

        mock_form_version.return_value = {
            "id": 3,
        }

        mock_create.return_value = {
            "survey_record_id": 101,
            "engineering_asset_id": 201,
            "business_code": "1-01-01-06-001",
        }

        self._seed_ownership()

        self.page.get_field_widget("asset_name").setText("测试涵洞")

        result = self.page._save_current_record(show_message=False)

        self.assertEqual(
            result["survey_record_id"],
            101,
        )

        self.assertEqual(
            self.page.editing_record_id,
            101,
        )

        self.assertEqual(
            self.page.editing_record_status,
            "draft",
        )

        self.assertFalse(self.page.department_combo.isEnabled())

        self.assertFalse(self.page.is_dirty)

        kwargs = mock_create.call_args.kwargs

        self.assertEqual(
            kwargs["organization_unit_id"],
            20,
        )

        self.assertEqual(
            kwargs["canal_unit_id"],
            30,
        )

        self.assertEqual(
            kwargs["payload"]["asset_name"],
            "测试涵洞",
        )

    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "update_engineering_record"
    )
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_current_form_version"
    )
    @patch("pages.components." "generic_engineering_survey_page." "get_current_context")
    def test_second_save_updates_same_draft(
        self,
        mock_context,
        mock_form_version,
        mock_update,
    ):
        mock_context.return_value = {
            "project_id": 1,
            "batch_id": 2,
        }

        mock_form_version.return_value = {
            "id": 3,
        }

        self._seed_ownership()

        self.page.editing_record_id = 102
        self.page.editing_record_status = "draft"

        self.page.get_field_widget("asset_name").setText("修改后的涵洞")

        self.page._save_current_record(show_message=False)

        mock_update.assert_called_once()

        kwargs = mock_update.call_args.kwargs

        self.assertEqual(
            kwargs["survey_record_id"],
            102,
        )

        self.assertEqual(
            kwargs["payload"]["asset_name"],
            "修改后的涵洞",
        )

        self.assertEqual(
            self.page.editing_record_id,
            102,
        )

    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_canal_units_for_organization"
    )
    @patch("pages.components." "generic_engineering_survey_page." "get_water_offices")
    @patch("pages.components." "generic_engineering_survey_page." "get_departments")
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_current_form_version"
    )
    @patch("pages.components." "generic_engineering_survey_page." "get_current_context")
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "load_engineering_record_bundle"
    )
    def test_load_record_restores_asset_identity_and_locks_ownership(
        self,
        mock_bundle,
        mock_context,
        mock_form_version,
        mock_departments,
        mock_offices,
        mock_canals,
    ):
        mock_context.return_value = {
            "project_id": 1,
            "batch_id": 2,
        }

        mock_form_version.return_value = {
            "id": 3,
        }

        mock_departments.return_value = [
            {
                "id": 10,
                "name": "测试基层处",
                "business_code": "1",
                "status": "active",
            }
        ]

        mock_offices.return_value = [
            {
                "id": 20,
                "name": "测试水管所",
                "business_code": "01",
                "status": "active",
            }
        ]

        mock_canals.return_value = [
            {
                "id": 30,
                "name": "测试干渠",
                "canal_level": "01",
            }
        ]

        mock_bundle.return_value = {
            "record": {
                "survey_record_id": 103,
                "record_status": "draft",
                "business_code": "1-01-01-06-005",
                "asset_name": "数据库中的涵洞",
                "single_stake_text": "CH8+500",
                "single_stake_value": 8500.0,
                "department_id": 10,
                "office_id": 20,
                "canal_id": 30,
                "record_data": {
                    # 故意放旧副本，
                    # 验证 EngineeringAsset 优先。
                    "asset_name": "旧名称",
                    "stake": "CH1+000",
                    "design_flow": 6.5,
                },
                "survey_date": "2026-09-15",
                "overall_grade": None,
                "survey_comment": "",
            },
            "inspection_results": [],
        }

        self.page.load_record(103)

        self.assertEqual(
            self.page.get_field_widget("asset_name").text(),
            "数据库中的涵洞",
        )

        self.assertEqual(
            self.page.get_field_widget("stake").text(),
            "CH8+500",
        )

        self.assertEqual(
            self.page.business_code_edit.text(),
            "1-01-01-06-005",
        )

        self.assertFalse(self.page.department_combo.isEnabled())

        self.assertEqual(
            self.page.editing_record_status,
            "draft",
        )

        self.assertFalse(self.page.is_dirty)

    def _fill_complete_form(
        self,
    ):
        """
        按FORM_2_6定义生成一份
        可以通过完成校验的页面数据。
        """

        for field in FORM_2_6.fields:
            widget = (
                self.page.get_field_widget(
                    field.key
                )
            )

            if field.key == "asset_name":
                value = "完整测试涵洞"

            elif field.key == "stake":
                value = "CH10+500"

            elif (
                field.key
                == "renovation_date"
            ):
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
                raise AssertionError(
                    "测试未覆盖字段类型："
                    f"{field.input_type}"
                )

            widget.setText(
                value
            )

        for item in (
            FORM_2_6.evaluation_items
        ):
            item_code = item[
                "item_code"
            ]

            controls = (
                self.page
                .evaluation_section
                .grade_buttons[
                    item_code
                ]
            )

            controls["A"].setChecked(
                True
            )

        self.page.set_overall_grade(
            "A"
        )

        self.page.survey_date_edit.setText(
            "2026-09-15"
        )

        self.page.survey_comment_edit.setPlainText(
            "完整测试调查意见。"
        )

    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "update_engineering_record"
    )
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_current_form_version"
    )
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_current_context"
    )
    def test_completed_record_can_save_valid_modification(
        self,
        mock_context,
        mock_form_version,
        mock_update,
    ):
        mock_context.return_value = {
            "project_id": 1,
            "batch_id": 2,
        }

        mock_form_version.return_value = {
            "id": 3,
        }

        self._seed_ownership()
        self._fill_complete_form()

        self.page.editing_record_id = 201
        self.page.editing_record_status = (
            "completed"
        )

        self.page._apply_record_mode()

        result = (
            self.page
            ._save_current_record(
                show_message=False
            )
        )

        self.assertEqual(
            result[
                "survey_record_id"
            ],
            201,
        )

        mock_update.assert_called_once()

        self.assertEqual(
            self.page
            .editing_record_status,
            "completed",
        )

        self.assertTrue(
            self.page.save_button.isEnabled()
        )

        self.assertFalse(
            self.page
            .complete_button.isEnabled()
        )


    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "update_engineering_record"
    )
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_current_form_version"
    )
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_current_context"
    )
    def test_completed_record_rejects_incomplete_modification(
        self,
        mock_context,
        mock_form_version,
        mock_update,
    ):
        mock_context.return_value = {
            "project_id": 1,
            "batch_id": 2,
        }

        mock_form_version.return_value = {
            "id": 3,
        }

        self._seed_ownership()
        self._fill_complete_form()

        self.page.editing_record_id = 202
        self.page.editing_record_status = (
            "completed"
        )

        self.page.get_field_widget(
            "design_flow"
        ).clear()

        with self.assertRaisesRegex(
            ValueError,
            "设计流量",
        ):
            self.page._save_current_record(
                show_message=False
            )

        mock_update.assert_not_called()


    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "complete_engineering_record"
    )
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_current_form_version"
    )
    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "get_current_context"
    )
    @patch(
        "PySide6.QtWidgets."
        "QMessageBox.question",
        return_value=(
            QMessageBox.StandardButton.Yes
        ),
    )
    @patch(
        "PySide6.QtWidgets."
        "QMessageBox.information"
    )
    def test_existing_draft_can_complete(
        self,
        mock_information,
        mock_question,
        mock_context,
        mock_form_version,
        mock_complete,
    ):
        mock_context.return_value = {
            "project_id": 1,
            "batch_id": 2,
        }

        mock_form_version.return_value = {
            "id": 3,
        }

        mock_complete.return_value = {
            "survey_record_id": 203,
            "inspection_count": 11,
        }

        self._seed_ownership()
        self._fill_complete_form()

        self.page.editing_record_id = 203
        self.page.editing_record_status = (
            "draft"
        )

        result = (
            self.page.complete_survey()
        )

        self.assertIsNotNone(
            result
        )

        self.assertEqual(
            self.page
            .editing_record_status,
            "completed",
        )

        self.assertFalse(
            self.page
            .complete_button
            .isEnabled()
        )

        mock_complete.assert_called_once()


    @patch(
        "pages.components."
        "generic_engineering_survey_page."
        "complete_engineering_record"
    )
    @patch(
        "PySide6.QtWidgets."
        "QMessageBox.warning"
    )
    def test_invalid_form_does_not_complete(
        self,
        mock_warning,
        mock_complete,
    ):
        self.page.editing_record_id = 204
        self.page.editing_record_status = (
            "draft"
        )

        result = (
            self.page.complete_survey()
        )

        self.assertIsNone(
            result
        )

        mock_complete.assert_not_called()

        mock_warning.assert_called_once()

if __name__ == "__main__":
    unittest.main()
