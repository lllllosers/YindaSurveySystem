import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from forms.engineering.form_2_5 import (
    FORM_2_5,
)

from services.tunnel_evaluation import (
    TUNNEL_EVALUATION_ITEMS,
)


class Form25DefinitionTestCase(
    unittest.TestCase,
):
    """
    附表2.5隧洞正式 definition golden contract。

    本测试锁定：
    - 表单身份；
    - range 工程位置；
    - 字段及类型；
    - 页面布局；
    - 正式评价项目；
    - 正式原文中的特殊文本。
    """

    def test_identity_contract(
        self,
    ):
        self.assertEqual(
            FORM_2_5.form_code,
            "form_2_5",
        )

        self.assertEqual(
            FORM_2_5.form_number,
            "2.5",
        )

        self.assertEqual(
            FORM_2_5.form_name,
            "隧洞工程状况调查表",
        )

        self.assertEqual(
            FORM_2_5.asset_type,
            "tunnel",
        )

        self.assertEqual(
            FORM_2_5.business_type_code,
            "05",
        )

        self.assertEqual(
            FORM_2_5.asset_name_field,
            "asset_name",
        )

    def test_position_contract(
        self,
    ):
        position = FORM_2_5.position

        self.assertEqual(
            position.kind,
            "range",
        )

        self.assertEqual(
            position.start_stake_field,
            "start_stake",
        )

        self.assertEqual(
            position.start_stake_value_key,
            "start_stake_value",
        )

        self.assertEqual(
            position.end_stake_field,
            "end_stake",
        )

        self.assertEqual(
            position.end_stake_value_key,
            "end_stake_value",
        )

        self.assertIsNone(
            position.single_stake_field
        )

        self.assertIsNone(
            position.single_stake_value_key
        )

    def test_field_contract(
        self,
    ):
        expected_keys = (
            "asset_name",
            "start_stake",
            "end_stake",
            "design_flow",
            "structure_grade",
            "build_date",
            "renovation_date",
            "length",
            "increased_flow",
            "lining_form",
            "lining_thickness",
            "concrete_strength",
            "inlet_outlet_bottom_elevation",
            "longitudinal_slope",
            "section_form",
            "section_width",
            "section_height",
            "cover_thickness",
        )

        self.assertEqual(
            tuple(
                field.key
                for field in FORM_2_5.fields
            ),
            expected_keys,
        )

        self.assertEqual(
            len(FORM_2_5.fields),
            18,
        )

    def test_only_renovation_date_is_optional(
        self,
    ):
        optional_fields = {
            field.key
            for field in FORM_2_5.fields
            if not field.required
        }

        self.assertEqual(
            optional_fields,
            {
                "renovation_date",
            },
        )

    def test_field_types_contract(
        self,
    ):
        field_map = FORM_2_5.field_map

        expected_types = {
            "asset_name": "text",
            "start_stake": "stake",
            "end_stake": "stake",
            "design_flow": "decimal",
            "structure_grade": "text",
            "build_date": "month",
            "renovation_date": "month",
            "length": "decimal",
            "increased_flow": "decimal",
            "lining_form": "text",
            "lining_thickness": "decimal",
            "concrete_strength": "text",
            "inlet_outlet_bottom_elevation": "text",
            "longitudinal_slope": "decimal",
            "section_form": "text",
            "section_width": "decimal",
            "section_height": "decimal",
            "cover_thickness": "decimal",
        }

        actual_types = {
            key: field_map[key].input_type
            for key in expected_types
        }

        self.assertEqual(
            actual_types,
            expected_types,
        )

    def test_units_contract(
        self,
    ):
        field_map = FORM_2_5.field_map

        self.assertEqual(
            field_map["design_flow"].unit,
            "m³/s",
        )

        self.assertEqual(
            field_map["increased_flow"].unit,
            "m³/s",
        )

        self.assertEqual(
            field_map["longitudinal_slope"].unit,
            "n/1000",
        )

        for key in (
            "length",
            "lining_thickness",
            "inlet_outlet_bottom_elevation",
            "section_width",
            "section_height",
            "cover_thickness",
        ):
            self.assertIsNone(
                field_map[key].unit
            )

    def test_section_layout_contract(
        self,
    ):
        self.assertEqual(
            len(FORM_2_5.sections),
            2,
        )

        self.assertEqual(
            FORM_2_5.sections[0].title,
            "二、工程基本信息",
        )

        self.assertEqual(
            FORM_2_5.sections[1].title,
            "三、结构与断面参数",
        )

        first_section_keys = tuple(
            row.field_keys[0]
            for row
            in FORM_2_5.sections[0].rows
        )

        self.assertEqual(
            first_section_keys,
            (
                "asset_name",
                "start_stake",
                "end_stake",
                "design_flow",
                "structure_grade",
                "build_date",
                "renovation_date",
                "length",
                "increased_flow",
            ),
        )

        second_section_keys = tuple(
            row.field_keys[0]
            for row
            in FORM_2_5.sections[1].rows
        )

        self.assertEqual(
            second_section_keys,
            (
                "lining_form",
                "lining_thickness",
                "concrete_strength",
                "inlet_outlet_bottom_elevation",
                "longitudinal_slope",
                "section_form",
                "section_width",
                "section_height",
                "cover_thickness",
            ),
        )

    def test_evaluation_contract(
        self,
    ):
        self.assertEqual(
            len(FORM_2_5.evaluation_items),
            13,
        )

        self.assertEqual(
            FORM_2_5.evaluation_items,
            tuple(
                TUNNEL_EVALUATION_ITEMS
            ),
        )

        expected_item_codes = (
            "hydraulic_inlet_outlet_flow",
            "hydraulic_inlet_outlet_level",
            "hydraulic_flow_capacity",
            "hydraulic_sedimentation",
            "deformation_rock_lining",
            "deformation_inlet_outlet_slopes",
            "damage_tunnel_body",
            "damage_inlet_outlet_face_transition",
            "damage_carbonation_depth",
            "damage_concrete_strength",
            "geology_surrounding_rock",
            "geology_groundwater_level",
            "geology_outer_slope",
        )

        actual_item_codes = tuple(
            item["item_code"]
            for item
            in FORM_2_5.evaluation_items
        )

        self.assertEqual(
            actual_item_codes,
            expected_item_codes,
        )

    def test_evaluation_source_text_fidelity(
        self,
    ):
        """
        锁定正式附表2.5评价原文。

        即使正式源文字看起来存在重复、
        标点或措辞异常，也不能在迁移中
        擅自进行语言修订。
        """

        items = FORM_2_5.evaluation_items

        expected_categories = (
            "水力条件",
            "水力条件",
            "水力条件",
            "水力条件",
            "衬砌结构变形",
            "衬砌结构变形",
            "衬砌结构破损",
            "衬砌结构破损",
            "衬砌结构破损",
            "衬砌结构破损",
            "洞线地质",
            "洞线地质",
            "洞线地质",
        )

        self.assertEqual(
            tuple(
                item["category"]
                for item in items
            ),
            expected_categories,
        )

        expected_item_names = (
            "进、出口流态",
            "进、出口水位",
            "过水流量",
            "冲淤情况",
            "洞身围岩及其衬砌结构",
            "进、出口渐变段，洞脸边坡及洞线外侧边坡",
            "洞身",
            "进、出口洞脸及渐变段",
            "混凝土碳化深度",
            "混凝土强度",
            "洞身围岩",
            "洞线地下水位",
            "隧洞外侧边坡",
        )

        self.assertEqual(
            tuple(
                item["item_name"]
                for item in items
            ),
            expected_item_names,
        )

        for item in items:
            with self.subTest(
                item_code=item["item_code"],
            ):
                self.assertEqual(
                    set(
                        item["standards"].keys()
                    ),
                    {
                        "A",
                        "B",
                        "C",
                        "D",
                    },
                )

        # 正式原文中的特殊文本锁定。
        self.assertIn(
            "0.2~0.3mm",
            items[6]["standards"]["C"],
        )

        self.assertIn(
            "基本基本完好",
            items[7]["standards"]["B"],
        )

        self.assertEqual(
            items[8]["standards"]["A"],
            items[8]["standards"]["B"],
        )

        self.assertTrue(
            items[5]["standards"]["D"].endswith(
                "洞脸边坡滑。"
            )
        )

    def test_grade_contract(
        self,
    ):
        self.assertEqual(
            FORM_2_5.grade_options,
            (
                "A",
                "B",
                "C",
                "D",
            ),
        )

        self.assertEqual(
            FORM_2_5.evaluation_title,
            "四、分项评价",
        )

        self.assertEqual(
            FORM_2_5.conclusion_title,
            "五、调查结论",
        )


if __name__ == "__main__":
    unittest.main()