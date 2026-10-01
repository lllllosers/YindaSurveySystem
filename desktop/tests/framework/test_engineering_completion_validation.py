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


from forms.engineering.validation import (
    validate_completion,
)

from tests.framework.engineering_test_fixtures import (
    TEST_POINT_DEFINITION,
    TEST_RANGE_DEFINITION,
    build_valid_point_payload,
    build_valid_range_payload,
)


class EngineeringCompletionValidationTestCase(
    unittest.TestCase,
):
    def test_valid_point_payload_passes(
        self,
    ):
        payload = build_valid_point_payload()

        errors = validate_completion(
            TEST_POINT_DEFINITION,
            payload,
        )

        self.assertEqual(
            errors,
            [],
        )

    def test_required_fields_are_checked(
        self,
    ):
        payload = build_valid_point_payload()

        payload["record_data"]["asset_name"] = None

        payload["record_data"]["design_flow"] = None

        errors = validate_completion(
            TEST_POINT_DEFINITION,
            payload,
        )

        self.assertIn(
            "工程名称不能为空。",
            errors,
        )

        self.assertIn(
            "设计流量不能为空。",
            errors,
        )

    def test_optional_field_can_be_blank(
        self,
    ):
        payload = build_valid_point_payload()

        payload["record_data"]["renovation_date"] = None

        errors = validate_completion(
            TEST_POINT_DEFINITION,
            payload,
        )

        self.assertEqual(
            errors,
            [],
        )

    def test_missing_evaluation_is_rejected(
        self,
    ):
        payload = build_valid_point_payload()

        missing_item = TEST_POINT_DEFINITION.evaluation_items[0]

        payload["inspection_results"] = [
            result
            for result in payload["inspection_results"]
            if result["item_code"] != missing_item["item_code"]
        ]

        errors = validate_completion(
            TEST_POINT_DEFINITION,
            payload,
        )

        self.assertIn(
            (f"{missing_item['item_name']}" "未完成评价。"),
            errors,
        )

    def test_conclusion_is_required(
        self,
    ):
        payload = build_valid_point_payload()

        payload["overall_grade"] = None
        payload["survey_date"] = None
        payload["survey_comment"] = "   "

        errors = validate_completion(
            TEST_POINT_DEFINITION,
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
        payload = build_valid_range_payload()

        payload["record_data"].update(
            {
                "start_stake": "CH2+000",
                "start_stake_value": 2000.0,
                "end_stake": "CH1+000",
                "end_stake_value": 1000.0,
            }
        )

        payload["position"].update(
            {
                "start_stake_text": "CH2+000",
                "start_stake_value": 2000.0,
                "end_stake_text": "CH1+000",
                "end_stake_value": 1000.0,
            }
        )

        errors = validate_completion(
            TEST_RANGE_DEFINITION,
            payload,
        )

        self.assertIn(
            "终止桩号不能小于起始桩号。",
            errors,
        )

    def test_invalid_month_is_rejected(
        self,
    ):
        payload = build_valid_point_payload()

        payload["record_data"]["build_date"] = "2026-13"

        errors = validate_completion(
            TEST_POINT_DEFINITION,
            payload,
        )

        self.assertIn(
            ("建成年月不是有效的 " "YYYY-MM 日期。"),
            errors,
        )

    def test_invalid_survey_date_is_rejected(
        self,
    ):
        payload = build_valid_point_payload()

        payload["survey_date"] = "2026-02-30"

        errors = validate_completion(
            TEST_POINT_DEFINITION,
            payload,
        )

        self.assertIn(
            ("调查时间不是有效的 " "YYYY-MM-DD 日期。"),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
