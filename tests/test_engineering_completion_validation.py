import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from forms.engineering.form_2_6 import (
    FORM_2_6,
)

from forms.engineering.models import (
    EngineeringFormDefinition,
    FieldDefinition,
    FieldRowDefinition,
    FormSectionDefinition,
    PositionDefinition,
)

from forms.engineering.validation import (
    validate_completion,
)


def build_valid_form_2_6_payload():
    record_data = {}

    for field in FORM_2_6.fields:
        if field.key == "renovation_date":
            record_data[field.key] = None

        elif field.input_type == "text":
            record_data[field.key] = "测试"

        elif field.input_type in (
            "decimal",
            "signed_decimal",
        ):
            record_data[field.key] = 1.0

        elif field.input_type == "integer":
            record_data[field.key] = 1

        elif field.input_type == "month":
            record_data[field.key] = "2026-01"

        elif field.input_type == "stake":
            record_data[field.key] = "CH1+000"

        else:
            raise AssertionError("测试未覆盖字段类型：" f"{field.input_type}")

    record_data["stake_value"] = 1000.0

    return {
        "asset_name": "测试涵洞",
        "record_data": record_data,
        "position": {
            "kind": "point",
            "single_stake_text": ("CH1+000"),
            "single_stake_value": (1000.0),
        },
        "inspection_results": [
            {
                "item_code": (item["item_code"]),
                "grade": "A",
            }
            for item in FORM_2_6.evaluation_items
        ],
        "survey_date": ("2026-09-15"),
        "overall_grade": "A",
        "survey_comment": ("测试调查意见"),
    }


class EngineeringCompletionValidationTestCase(unittest.TestCase):
    def test_valid_form_2_6_payload_passes(
        self,
    ):
        payload = build_valid_form_2_6_payload()

        errors = validate_completion(
            FORM_2_6,
            payload,
        )

        self.assertEqual(
            errors,
            [],
        )

    def test_required_fields_are_checked(
        self,
    ):
        payload = build_valid_form_2_6_payload()

        payload["record_data"]["asset_name"] = None

        payload["record_data"]["design_flow"] = None

        errors = validate_completion(
            FORM_2_6,
            payload,
        )

        self.assertIn(
            "名称不能为空。",
            errors,
        )

        self.assertIn(
            "设计流量不能为空。",
            errors,
        )

    def test_optional_field_can_be_blank(
        self,
    ):
        payload = build_valid_form_2_6_payload()

        payload["record_data"]["renovation_date"] = None

        errors = validate_completion(
            FORM_2_6,
            payload,
        )

        self.assertEqual(
            errors,
            [],
        )

    def test_missing_evaluation_is_rejected(
        self,
    ):
        payload = build_valid_form_2_6_payload()

        missing_item = FORM_2_6.evaluation_items[0]

        payload["inspection_results"] = [
            result
            for result in payload["inspection_results"]
            if result["item_code"] != missing_item["item_code"]
        ]

        errors = validate_completion(
            FORM_2_6,
            payload,
        )

        self.assertIn(
            (f"{missing_item['item_name']}" "未完成评价。"),
            errors,
        )

    def test_conclusion_is_required(
        self,
    ):
        payload = build_valid_form_2_6_payload()

        payload["overall_grade"] = None

        payload["survey_date"] = None

        payload["survey_comment"] = "   "

        errors = validate_completion(
            FORM_2_6,
            payload,
        )

        self.assertIn(
            "请选择工程状况类别。",
            errors,
        )

        self.assertIn(
            "请填写调查时间。",
            errors,
        )

        self.assertIn(
            "请填写调查意见与建议。",
            errors,
        )

    def test_range_end_cannot_precede_start(
        self,
    ):
        range_definition = EngineeringFormDefinition(
            form_code=("form_2_test_range"),
            form_number="test",
            form_name="测试区间表",
            asset_type=("test_range"),
            business_type_code="99",
            asset_name_field=("asset_name"),
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
                    key="asset_name",
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
                        FieldRowDefinition(("asset_name",)),
                        FieldRowDefinition(("start_stake",)),
                        FieldRowDefinition(("end_stake",)),
                    ),
                ),
            ),
            evaluation_items=(
                {
                    "item_code": ("test_item"),
                    "category": ("测试"),
                    "item_name": ("测试评价项"),
                    "standards": {
                        "A": "A",
                        "B": "B",
                        "C": "C",
                        "D": "D",
                    },
                },
            ),
        )

        payload = {
            "asset_name": "测试渠段",
            "record_data": {
                "asset_name": ("测试渠段"),
                "start_stake": ("CH2+000"),
                "start_stake_value": (2000.0),
                "end_stake": ("CH1+000"),
                "end_stake_value": (1000.0),
            },
            "position": {
                "kind": "range",
                "start_stake_text": ("CH2+000"),
                "start_stake_value": (2000.0),
                "end_stake_text": ("CH1+000"),
                "end_stake_value": (1000.0),
            },
            "inspection_results": [
                {
                    "item_code": ("test_item"),
                    "grade": "A",
                },
            ],
            "survey_date": ("2026-09-15"),
            "overall_grade": "A",
            "survey_comment": ("测试意见"),
        }

        errors = validate_completion(
            range_definition,
            payload,
        )

        self.assertIn(
            ("终止桩号不能小于" "起始桩号。"),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
