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


from forms.engineering.models import (
    EngineeringFormDefinition,
    FieldDefinition,
    FieldRowDefinition,
    FormSectionDefinition,
    PositionDefinition,
)

TEST_EVALUATION_ITEMS = (
    {
        "item_code": "test_item",
        "category": "测试类别",
        "item_name": "测试项目",
        "standards": {
            "A": "A级",
            "B": "B级",
            "C": "C级",
            "D": "D级",
        },
    },
)


class EngineeringFormDefinitionTestCase(unittest.TestCase):
    def test_point_definition_is_valid(
        self,
    ):
        definition = EngineeringFormDefinition(
            form_code="form_2_99",
            form_number="2.99",
            form_name="测试点工程",
            asset_type="test_point",
            business_type_code="99",
            asset_name_field=("asset_name"),
            position=(
                PositionDefinition.point(
                    stake_field="stake",
                    stake_value_key=("stake_value"),
                )
            ),
            fields=(
                FieldDefinition(
                    key="asset_name",
                    label="名称",
                ),
                FieldDefinition(
                    key="stake",
                    label="桩号",
                    input_type="stake",
                ),
                FieldDefinition(
                    key="design_flow",
                    label="设计流量",
                    input_type="decimal",
                    unit="m³/s",
                ),
            ),
            sections=(
                FormSectionDefinition(
                    title=("二、工程基本信息"),
                    rows=(
                        FieldRowDefinition(("asset_name",)),
                        FieldRowDefinition(("stake",)),
                        FieldRowDefinition(("design_flow",)),
                    ),
                ),
            ),
            evaluation_items=(TEST_EVALUATION_ITEMS),
        )

        self.assertEqual(
            definition.position.kind,
            "point",
        )

        self.assertEqual(
            definition.field_map["design_flow"].display_label,
            "设计流量（m³/s）",
        )

    def test_range_definition_is_valid(
        self,
    ):
        definition = EngineeringFormDefinition(
            form_code="form_2_98",
            form_number="2.98",
            form_name="测试区间工程",
            asset_type="test_range",
            business_type_code="98",
            asset_name_field="name",
            position=(
                PositionDefinition.range(
                    start_stake_field=("start_stake"),
                    start_stake_value_key=("start_stake_value"),
                    end_stake_field=("end_stake"),
                    end_stake_value_key=("end_stake_value"),
                )
            ),
            fields=(
                FieldDefinition(
                    key="name",
                    label="名称",
                ),
                FieldDefinition(
                    key="start_stake",
                    label="起始桩号",
                    input_type="stake",
                ),
                FieldDefinition(
                    key="end_stake",
                    label="终止桩号",
                    input_type="stake",
                ),
            ),
            sections=(
                FormSectionDefinition(
                    title=("二、工程基本信息"),
                    rows=(
                        FieldRowDefinition(("name",)),
                        FieldRowDefinition(("start_stake",)),
                        FieldRowDefinition(("end_stake",)),
                    ),
                ),
            ),
            evaluation_items=(TEST_EVALUATION_ITEMS),
        )

        self.assertEqual(
            definition.position.kind,
            "range",
        )

    def test_composite_row_is_valid(
        self,
    ):
        definition = EngineeringFormDefinition(
            form_code="form_2_97",
            form_number="2.97",
            form_name="测试组合字段",
            asset_type="test_composite",
            business_type_code="97",
            asset_name_field="name",
            position=(
                PositionDefinition.point(
                    stake_field="stake",
                    stake_value_key=("stake_value"),
                )
            ),
            fields=(
                FieldDefinition(
                    key="name",
                    label="名称",
                ),
                FieldDefinition(
                    key="stake",
                    label="桩号",
                    input_type="stake",
                ),
                FieldDefinition(
                    key="width",
                    label="宽",
                    input_type="decimal",
                ),
                FieldDefinition(
                    key="height",
                    label="高",
                    input_type="decimal",
                ),
            ),
            sections=(
                FormSectionDefinition(
                    title="三、结构参数",
                    rows=(
                        FieldRowDefinition(("name",)),
                        FieldRowDefinition(("stake",)),
                        FieldRowDefinition(
                            (
                                "width",
                                "height",
                            ),
                            label=("断面尺寸" "（宽×高）"),
                            separator="×",
                        ),
                    ),
                ),
            ),
            evaluation_items=(TEST_EVALUATION_ITEMS),
        )

        row = definition.sections[0].rows[2]

        self.assertEqual(
            row.field_keys,
            (
                "width",
                "height",
            ),
        )

        self.assertEqual(
            row.separator,
            "×",
        )

    def test_three_level_evaluation_is_valid(
        self,
    ):
        items = (
            {
                "item_code": "item_1",
                "category": "测试",
                "item_name": "测试",
                "standards": {
                    "A": "A",
                    "B": "B",
                    "C": "C",
                },
            },
        )

        definition = EngineeringFormDefinition(
            form_code="form_2_96",
            form_number="2.96",
            form_name="三级评价测试",
            asset_type="test_grade",
            business_type_code="96",
            asset_name_field="name",
            position=(
                PositionDefinition.point(
                    stake_field="stake",
                    stake_value_key=("stake_value"),
                )
            ),
            fields=(
                FieldDefinition(
                    key="name",
                    label="名称",
                ),
                FieldDefinition(
                    key="stake",
                    label="桩号",
                    input_type="stake",
                ),
            ),
            sections=(
                FormSectionDefinition(
                    title="二、基本信息",
                    rows=(
                        FieldRowDefinition(("name",)),
                        FieldRowDefinition(("stake",)),
                    ),
                ),
            ),
            evaluation_items=items,
            grade_options=(
                "A",
                "B",
                "C",
            ),
        )

        self.assertEqual(
            definition.grade_options,
            (
                "A",
                "B",
                "C",
            ),
        )

    def test_choice_field_definition_is_valid(
        self,
    ):
        field = FieldDefinition(
            key="has_flood_control",
            label="有无防洪设施",
            input_type="choice",
            choices=(
                " 有 ",
                "无",
            ),
        )

        self.assertEqual(
            field.choices,
            (
                "有",
                "无",
            ),
        )

    def test_choice_field_requires_options(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "候选项",
        ):
            FieldDefinition(
                key="has_flood_control",
                label="有无防洪设施",
                input_type="choice",
            )

    def test_non_choice_field_rejects_choices(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "只有 choice",
        ):
            FieldDefinition(
                key="name",
                label="名称",
                input_type="text",
                choices=(
                    "A",
                    "B",
                ),
            )

    def test_invalid_position_field_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "桩号字段",
        ):
            EngineeringFormDefinition(
                form_code="form_2_95",
                form_number="2.95",
                form_name="错误定义",
                asset_type="invalid",
                business_type_code="95",
                asset_name_field="name",
                position=(
                    PositionDefinition.point(
                        stake_field=("missing_stake"),
                        stake_value_key=("stake_value"),
                    )
                ),
                fields=(
                    FieldDefinition(
                        key="name",
                        label="名称",
                    ),
                ),
                sections=(
                    FormSectionDefinition(
                        title="二、基本信息",
                        rows=(FieldRowDefinition(("name",)),),
                    ),
                ),
                evaluation_items=(TEST_EVALUATION_ITEMS),
            )


if __name__ == "__main__":
    unittest.main()
