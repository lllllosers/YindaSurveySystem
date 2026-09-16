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


from forms.engineering.form_2_6 import (
    FORM_2_6,
)

from services.culvert_evaluation import (
    CULVERT_EVALUATION_ITEMS,
)


class Form26DefinitionTestCase(
    unittest.TestCase,
):

    def test_identity_contract(
        self,
    ):
        self.assertEqual(
            FORM_2_6.form_code,
            "form_2_6",
        )

        self.assertEqual(
            FORM_2_6.form_number,
            "2.6",
        )

        self.assertEqual(
            FORM_2_6.form_name,
            "涵洞（暗涵）工程状况调查表",
        )

        self.assertEqual(
            FORM_2_6.asset_type,
            "culvert",
        )

        self.assertEqual(
            FORM_2_6.business_type_code,
            "06",
        )

        self.assertEqual(
            FORM_2_6.asset_name_field,
            "asset_name",
        )

    def test_position_contract(
        self,
    ):
        position = FORM_2_6.position

        self.assertEqual(
            position.kind,
            "point",
        )

        self.assertEqual(
            position.single_stake_field,
            "stake",
        )

        self.assertEqual(
            position.single_stake_value_key,
            "stake_value",
        )

    def test_field_contract(
        self,
    ):
        expected_keys = (
            "asset_name",
            "stake",
            "design_flow",
            "structure_grade",
            "build_date",
            "renovation_date",
            "length",
            "increased_flow",
            "structure_form",
            "main_structure_material",
            "concrete_strength",
            "cover_thickness",
            "soil_cover_thickness",
            "channel_width",
            "channel_depth",
            "channel_bottom_elevation",
        )

        self.assertEqual(
            tuple(field.key for field in FORM_2_6.fields),
            expected_keys,
        )

        self.assertEqual(
            len(FORM_2_6.fields),
            16,
        )

    def test_only_renovation_date_is_optional(
        self,
    ):
        optional_fields = {field.key for field in FORM_2_6.fields if not field.required}

        self.assertEqual(
            optional_fields,
            {
                "renovation_date",
            },
        )

    def test_field_types_contract(
        self,
    ):
        field_map = FORM_2_6.field_map

        expected_types = {
            "asset_name": "text",
            "stake": "stake",
            "design_flow": "decimal",
            "structure_grade": "text",
            "build_date": "month",
            "renovation_date": "month",
            "length": "decimal",
            "increased_flow": "decimal",
            "structure_form": "text",
            "main_structure_material": "text",
            "concrete_strength": "text",
            "cover_thickness": "decimal",
            "soil_cover_thickness": "decimal",
            "channel_width": "decimal",
            "channel_depth": "decimal",
            "channel_bottom_elevation": ("signed_decimal"),
        }

        actual_types = {key: field_map[key].input_type for key in expected_types}

        self.assertEqual(
            actual_types,
            expected_types,
        )

    def test_units_contract(
        self,
    ):
        field_map = FORM_2_6.field_map

        self.assertEqual(
            field_map["design_flow"].unit,
            "m³/s",
        )

        self.assertEqual(
            field_map["increased_flow"].unit,
            "m³/s",
        )

        self.assertIsNone(field_map["length"].unit)

        self.assertIsNone(field_map["cover_thickness"].unit)

        for key in (
            "soil_cover_thickness",
            "channel_width",
            "channel_depth",
            "channel_bottom_elevation",
        ):
            self.assertEqual(
                field_map[key].unit,
                "m",
            )

    def test_section_layout_contract(
        self,
    ):
        self.assertEqual(
            len(FORM_2_6.sections),
            2,
        )

        self.assertEqual(
            FORM_2_6.sections[0].title,
            "二、工程基本信息",
        )

        self.assertEqual(
            FORM_2_6.sections[1].title,
            "三、结构与断面参数",
        )

        first_section_keys = tuple(
            row.field_keys[0] for row in FORM_2_6.sections[0].rows
        )

        self.assertEqual(
            first_section_keys,
            (
                "asset_name",
                "stake",
                "design_flow",
                "structure_grade",
                "build_date",
                "renovation_date",
                "length",
                "increased_flow",
            ),
        )

        second_section_keys = tuple(
            row.field_keys[0] for row in FORM_2_6.sections[1].rows
        )

        self.assertEqual(
            second_section_keys,
            (
                "structure_form",
                "main_structure_material",
                "concrete_strength",
                "cover_thickness",
                "soil_cover_thickness",
                "channel_width",
                "channel_depth",
                "channel_bottom_elevation",
            ),
        )

    def test_evaluation_contract(
        self,
    ):
        self.assertEqual(
            len(FORM_2_6.evaluation_items),
            11,
        )

        self.assertEqual(
            FORM_2_6.evaluation_items,
            tuple(CULVERT_EVALUATION_ITEMS),
        )

        expected_item_codes = (
            "hydraulic_inlet_outlet_flow",
            "hydraulic_inlet_outlet_level",
            "hydraulic_flow_capacity",
            "hydraulic_sedimentation",
            "deformation_culvert_body_lining",
            "deformation_other_parts",
            "damage_culvert_body",
            "damage_other_structure",
            "damage_carbonation_depth",
            "damage_concrete_strength",
            "foundation_base",
        )

        actual_item_codes = tuple(
            item["item_code"] for item in FORM_2_6.evaluation_items
        )

        self.assertEqual(
            actual_item_codes,
            expected_item_codes,
        )

    def test_evaluation_source_text_fidelity(
        self,
    ):
        """
        锁定正式附表2.6评价内容。

        正式源中存在的特殊编号和文字
        不允许在开发过程中被自动纠正。
        """

        items = FORM_2_6.evaluation_items

        expected_categories = (
            "水力条件",
            "水力条件",
            "水力条件",
            "水力条件",
            "结构变形",
            "结构变形",
            "结构破损",
            "结构破损",
            "结构破损",
            "结构破损",
            "地基基础",
        )

        self.assertEqual(
            tuple(item["category"] for item in items),
            expected_categories,
        )

        expected_item_names = (
            "进、出口流态",
            "进、出口水位",
            "过流能力",
            "冲淤情况",
            "洞身衬砌结构变形",
            "其它部位结构变形",
            "洞身结构",
            "其它结构",
            "混凝土碳化深度",
            "混凝土强度",
            "地基基础",
        )

        self.assertEqual(
            tuple(item["item_name"] for item in items),
            expected_item_names,
        )

        for item in items:
            with self.subTest(
                item_code=item["item_code"],
            ):
                self.assertEqual(
                    set(item["standards"].keys()),
                    {
                        "A",
                        "B",
                        "C",
                        "D",
                    },
                )

        self.assertTrue(items[1]["standards"]["C"].startswith("②"))

        carbonation = items[8]["standards"]

        self.assertEqual(
            carbonation["A"],
            carbonation["B"],
        )

        self.assertIn(
            "剥蚀脱离",
            items[6]["standards"]["D"],
        )

    def test_grade_contract(
        self,
    ):
        self.assertEqual(
            FORM_2_6.grade_options,
            (
                "A",
                "B",
                "C",
                "D",
            ),
        )

        self.assertEqual(
            FORM_2_6.evaluation_title,
            "四、分项评价",
        )

        self.assertEqual(
            FORM_2_6.conclusion_title,
            "五、调查结论",
        )


if __name__ == "__main__":
    unittest.main()
