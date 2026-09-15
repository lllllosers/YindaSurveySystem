import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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

from forms.engineering.models import (
    EngineeringFormDefinition,
    FieldDefinition,
    FieldRowDefinition,
    FormSectionDefinition,
    PositionDefinition,
)

from forms.engineering.persistence import (
    complete_engineering_record,
    create_engineering_record,
    get_engineering_record,
    load_engineering_record_bundle,
    update_engineering_record,
)


def build_point_payload():
    record_data = {}

    for field in FORM_2_6.fields:
        if field.key == "asset_name":
            value = "测试涵洞"

        elif field.key == "stake":
            value = "CH1+100"

        elif field.key == "renovation_date":
            value = None

        elif field.input_type == "text":
            value = "测试"

        elif field.input_type in (
            "decimal",
            "signed_decimal",
        ):
            value = 1.0

        elif field.input_type == "integer":
            value = 1

        elif field.input_type == "month":
            value = "2026-01"

        else:
            raise AssertionError("测试未覆盖字段类型：" f"{field.input_type}")

        record_data[field.key] = value

    record_data["stake_value"] = 1100.0

    return {
        "asset_name": "测试涵洞",
        "record_data": record_data,
        "position": {
            "kind": "point",
            "single_stake_text": "CH1+100",
            "single_stake_value": 1100.0,
        },
        "inspection_results": [
            {
                "item_code": item["item_code"],
                "category": item["category"],
                "item_name": item["item_name"],
                "grade": "A",
                "description": None,
                "remark": None,
            }
            for item in FORM_2_6.evaluation_items
        ],
        "survey_date": "2026-09-15",
        "overall_grade": "A",
        "survey_comment": "测试意见",
    }


def build_range_definition():
    return EngineeringFormDefinition(
        form_code="form_2_test_range",
        form_number="test",
        form_name="测试区间工程",
        asset_type="test_range",
        business_type_code="99",
        asset_name_field="asset_name",
        position=PositionDefinition.range(
            start_stake_field="start_stake",
            start_stake_value_key=("start_stake_value"),
            end_stake_field="end_stake",
            end_stake_value_key=("end_stake_value"),
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
                title="二、工程基本信息",
                rows=(
                    FieldRowDefinition(("asset_name",)),
                    FieldRowDefinition(("start_stake",)),
                    FieldRowDefinition(("end_stake",)),
                ),
            ),
        ),
        evaluation_items=(
            {
                "item_code": "test_item",
                "category": "测试",
                "item_name": "测试项",
                "standards": {
                    "A": "A",
                    "B": "B",
                    "C": "C",
                    "D": "D",
                },
            },
        ),
    )


def build_range_payload():
    return {
        "asset_name": "测试区间工程",
        "record_data": {
            "asset_name": "测试区间工程",
            "start_stake": "CH1+000",
            "start_stake_value": 1000.0,
            "end_stake": "CH2+000",
            "end_stake_value": 2000.0,
        },
        "position": {
            "kind": "range",
            "start_stake_text": "CH1+000",
            "start_stake_value": 1000.0,
            "end_stake_text": "CH2+000",
            "end_stake_value": 2000.0,
        },
        "inspection_results": [],
        "survey_date": "2026-09-15",
        "overall_grade": None,
        "survey_comment": None,
    }


class EngineeringPersistenceTestCase(unittest.TestCase):
    @patch("forms.engineering.persistence." "create_engineering_survey")
    def test_point_create_routes_to_point_api(
        self,
        mock_create,
    ):
        mock_create.return_value = {
            "survey_record_id": 10,
        }

        result = create_engineering_record(
            FORM_2_6,
            project_id=1,
            survey_batch_id=2,
            form_version_id=3,
            organization_unit_id=4,
            canal_unit_id=5,
            business_code="TEST-001",
            payload=build_point_payload(),
        )

        self.assertEqual(
            result["survey_record_id"],
            10,
        )

        kwargs = mock_create.call_args.kwargs

        self.assertEqual(
            kwargs["asset_type"],
            "culvert",
        )

        self.assertEqual(
            kwargs["single_stake_text"],
            "CH1+100",
        )

        self.assertEqual(
            kwargs["single_stake_value"],
            1100.0,
        )

        self.assertEqual(
            kwargs["business_code"],
            "TEST-001",
        )

    @patch("forms.engineering.persistence." "create_range_engineering_survey")
    def test_range_create_routes_to_range_api(
        self,
        mock_create,
    ):
        definition = build_range_definition()

        mock_create.return_value = {
            "survey_record_id": 20,
        }

        result = create_engineering_record(
            definition,
            project_id=1,
            survey_batch_id=2,
            form_version_id=3,
            organization_unit_id=4,
            canal_unit_id=5,
            business_code="TEST-002",
            payload=build_range_payload(),
        )

        self.assertEqual(
            result["survey_record_id"],
            20,
        )

        kwargs = mock_create.call_args.kwargs

        self.assertEqual(
            kwargs["start_stake_value"],
            1000.0,
        )

        self.assertEqual(
            kwargs["end_stake_value"],
            2000.0,
        )

    @patch("forms.engineering.persistence." "update_point_engineering_survey")
    def test_point_update_routes_to_point_api(
        self,
        mock_update,
    ):
        update_engineering_record(
            FORM_2_6,
            survey_record_id=30,
            payload=build_point_payload(),
        )

        kwargs = mock_update.call_args.kwargs

        self.assertEqual(
            kwargs["survey_record_id"],
            30,
        )

        self.assertEqual(
            kwargs["form_code"],
            "form_2_6",
        )

        self.assertEqual(
            kwargs["single_stake_value"],
            1100.0,
        )

    @patch("forms.engineering.persistence." "update_range_engineering_survey")
    def test_range_update_routes_to_range_api(
        self,
        mock_update,
    ):
        definition = build_range_definition()

        update_engineering_record(
            definition,
            survey_record_id=40,
            payload=build_range_payload(),
        )

        kwargs = mock_update.call_args.kwargs

        self.assertEqual(
            kwargs["survey_record_id"],
            40,
        )

        self.assertEqual(
            kwargs["form_code"],
            "form_2_test_range",
        )

        self.assertEqual(
            kwargs["start_stake_value"],
            1000.0,
        )

        self.assertEqual(
            kwargs["end_stake_value"],
            2000.0,
        )

    @patch("forms.engineering.persistence." "get_point_engineering_record")
    def test_point_read_routes_to_point_api(
        self,
        mock_get,
    ):
        mock_get.return_value = {
            "survey_record_id": 50,
        }

        record = get_engineering_record(
            FORM_2_6,
            survey_record_id=50,
        )

        self.assertEqual(
            record["survey_record_id"],
            50,
        )

        mock_get.assert_called_once_with(
            survey_record_id=50,
            form_code="form_2_6",
        )

    @patch("forms.engineering.persistence." "get_range_engineering_record")
    def test_range_read_routes_to_range_api(
        self,
        mock_get,
    ):
        definition = build_range_definition()

        mock_get.return_value = {
            "survey_record_id": 60,
        }

        record = get_engineering_record(
            definition,
            survey_record_id=60,
        )

        self.assertEqual(
            record["survey_record_id"],
            60,
        )

        mock_get.assert_called_once_with(
            survey_record_id=60,
            form_code="form_2_test_range",
        )

    @patch("forms.engineering.persistence." "get_inspection_results")
    @patch("forms.engineering.persistence." "get_engineering_record")
    def test_bundle_loads_record_and_evaluations(
        self,
        mock_get_record,
        mock_get_results,
    ):
        mock_get_record.return_value = {
            "survey_record_id": 70,
        }

        mock_get_results.return_value = [
            {
                "item_code": "test_item",
                "grade": "B",
            }
        ]

        bundle = load_engineering_record_bundle(
            FORM_2_6,
            survey_record_id=70,
        )

        self.assertEqual(
            bundle["record"]["survey_record_id"],
            70,
        )

        self.assertEqual(
            bundle["inspection_results"][0]["grade"],
            "B",
        )

    @patch("forms.engineering.persistence." "get_inspection_results")
    @patch("forms.engineering.persistence." "get_engineering_record")
    def test_missing_record_returns_none(
        self,
        mock_get_record,
        mock_get_results,
    ):
        mock_get_record.return_value = None

        bundle = load_engineering_record_bundle(
            FORM_2_6,
            survey_record_id=999,
        )

        self.assertIsNone(bundle)

        mock_get_results.assert_not_called()

    @patch("forms.engineering.persistence." "complete_engineering_survey_record")
    @patch("forms.engineering.persistence." "update_engineering_record")
    @patch("forms.engineering.persistence." "get_engineering_record")
    def test_complete_valid_point_record(
        self,
        mock_get_record,
        mock_update,
        mock_complete,
    ):
        mock_get_record.return_value = {
            "survey_record_id": 80,
            "record_status": "draft",
        }

        mock_complete.return_value = {
            "survey_record_id": 80,
            "inspection_count": 11,
        }

        result = complete_engineering_record(
            FORM_2_6,
            survey_record_id=80,
            payload=(build_point_payload()),
        )

        self.assertEqual(
            result["inspection_count"],
            11,
        )

        mock_update.assert_called_once()

        kwargs = mock_complete.call_args.kwargs

        self.assertEqual(
            kwargs["form_code"],
            "form_2_6",
        )

        self.assertEqual(
            kwargs["position_kind"],
            "point",
        )

        self.assertEqual(
            len(kwargs["expected_item_codes"]),
            11,
        )

    @patch("forms.engineering.persistence." "complete_engineering_survey_record")
    @patch("forms.engineering.persistence." "update_engineering_record")
    @patch("forms.engineering.persistence." "get_engineering_record")
    def test_completed_record_cannot_complete_again(
        self,
        mock_get_record,
        mock_update,
        mock_complete,
    ):
        mock_get_record.return_value = {
            "survey_record_id": 81,
            "record_status": "completed",
        }

        with self.assertRaisesRegex(
            ValueError,
            "只有草稿记录",
        ):
            complete_engineering_record(
                FORM_2_6,
                survey_record_id=81,
                payload=(build_point_payload()),
            )

        mock_update.assert_not_called()

        mock_complete.assert_not_called()

    @patch("forms.engineering.persistence." "complete_engineering_survey_record")
    @patch("forms.engineering.persistence." "update_engineering_record")
    @patch("forms.engineering.persistence." "get_engineering_record")
    def test_invalid_payload_is_not_saved_on_completion(
        self,
        mock_get_record,
        mock_update,
        mock_complete,
    ):
        mock_get_record.return_value = {
            "survey_record_id": 82,
            "record_status": "draft",
        }

        payload = build_point_payload()

        payload["record_data"]["design_flow"] = None

        with self.assertRaisesRegex(
            ValueError,
            "设计流量",
        ):
            complete_engineering_record(
                FORM_2_6,
                survey_record_id=82,
                payload=payload,
            )

        mock_update.assert_not_called()

        mock_complete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
