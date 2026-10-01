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


from forms.engineering.persistence import (
    complete_engineering_record,
    create_engineering_record,
    get_engineering_record,
    load_engineering_record_bundle,
    update_engineering_record,
)

from tests.framework.engineering_test_fixtures import (
    TEST_POINT_DEFINITION,
    TEST_RANGE_DEFINITION,
    build_valid_point_payload,
    build_valid_range_payload,
)


class EngineeringPersistenceTestCase(
    unittest.TestCase,
):
    # =========================================================
    # 创建
    # =========================================================

    @patch("forms.engineering.persistence." "create_engineering_survey")
    def test_point_create_routes_to_point_api(
        self,
        mock_create,
    ):
        mock_create.return_value = {
            "survey_record_id": 10,
        }

        result = create_engineering_record(
            TEST_POINT_DEFINITION,
            project_id=1,
            survey_batch_id=2,
            form_version_id=3,
            organization_unit_id=4,
            canal_unit_id=5,
            business_code="TEST-001",
            payload=build_valid_point_payload(),
        )

        self.assertEqual(
            result["survey_record_id"],
            10,
        )

        kwargs = mock_create.call_args.kwargs

        self.assertEqual(
            kwargs["asset_type"],
            TEST_POINT_DEFINITION.asset_type,
        )

        self.assertEqual(
            kwargs["single_stake_text"],
            "CH1+000",
        )

        self.assertEqual(
            kwargs["single_stake_value"],
            1000.0,
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
        mock_create.return_value = {
            "survey_record_id": 20,
        }

        result = create_engineering_record(
            TEST_RANGE_DEFINITION,
            project_id=1,
            survey_batch_id=2,
            form_version_id=3,
            organization_unit_id=4,
            canal_unit_id=5,
            business_code="TEST-002",
            payload=build_valid_range_payload(),
        )

        self.assertEqual(
            result["survey_record_id"],
            20,
        )

        kwargs = mock_create.call_args.kwargs

        self.assertEqual(
            kwargs["asset_type"],
            TEST_RANGE_DEFINITION.asset_type,
        )

        self.assertEqual(
            kwargs["start_stake_value"],
            1000.0,
        )

        self.assertEqual(
            kwargs["end_stake_value"],
            2000.0,
        )

    # =========================================================
    # 更新
    # =========================================================

    @patch("forms.engineering.persistence." "update_point_engineering_survey")
    def test_point_update_routes_to_point_api(
        self,
        mock_update,
    ):
        update_engineering_record(
            TEST_POINT_DEFINITION,
            survey_record_id=30,
            payload=build_valid_point_payload(),
        )

        kwargs = mock_update.call_args.kwargs

        self.assertEqual(
            kwargs["survey_record_id"],
            30,
        )

        self.assertEqual(
            kwargs["form_code"],
            TEST_POINT_DEFINITION.form_code,
        )

        self.assertEqual(
            kwargs["single_stake_value"],
            1000.0,
        )

    @patch("forms.engineering.persistence." "update_range_engineering_survey")
    def test_range_update_routes_to_range_api(
        self,
        mock_update,
    ):
        update_engineering_record(
            TEST_RANGE_DEFINITION,
            survey_record_id=40,
            payload=build_valid_range_payload(),
        )

        kwargs = mock_update.call_args.kwargs

        self.assertEqual(
            kwargs["survey_record_id"],
            40,
        )

        self.assertEqual(
            kwargs["form_code"],
            TEST_RANGE_DEFINITION.form_code,
        )

        self.assertEqual(
            kwargs["start_stake_value"],
            1000.0,
        )

        self.assertEqual(
            kwargs["end_stake_value"],
            2000.0,
        )

    # =========================================================
    # 读取
    # =========================================================

    @patch("forms.engineering.persistence." "get_point_engineering_record")
    def test_point_read_routes_to_point_api(
        self,
        mock_get,
    ):
        mock_get.return_value = {
            "survey_record_id": 50,
        }

        record = get_engineering_record(
            TEST_POINT_DEFINITION,
            survey_record_id=50,
        )

        self.assertEqual(
            record["survey_record_id"],
            50,
        )

        mock_get.assert_called_once_with(
            survey_record_id=50,
            form_code=(TEST_POINT_DEFINITION.form_code),
        )

    @patch("forms.engineering.persistence." "get_range_engineering_record")
    def test_range_read_routes_to_range_api(
        self,
        mock_get,
    ):
        mock_get.return_value = {
            "survey_record_id": 60,
        }

        record = get_engineering_record(
            TEST_RANGE_DEFINITION,
            survey_record_id=60,
        )

        self.assertEqual(
            record["survey_record_id"],
            60,
        )

        mock_get.assert_called_once_with(
            survey_record_id=60,
            form_code=(TEST_RANGE_DEFINITION.form_code),
        )

    # =========================================================
    # 页面恢复数据 bundle
    # =========================================================

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
                "item_code": "test_item_1",
                "grade": "B",
            }
        ]

        bundle = load_engineering_record_bundle(
            TEST_POINT_DEFINITION,
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
            TEST_POINT_DEFINITION,
            survey_record_id=999,
        )

        self.assertIsNone(bundle)

        mock_get_results.assert_not_called()

    # =========================================================
    # 完成调查
    # =========================================================

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

        expected_item_codes = tuple(
            item["item_code"] for item in TEST_POINT_DEFINITION.evaluation_items
        )

        mock_complete.return_value = {
            "survey_record_id": 80,
            "inspection_count": len(expected_item_codes),
        }

        result = complete_engineering_record(
            TEST_POINT_DEFINITION,
            survey_record_id=80,
            payload=build_valid_point_payload(),
        )

        self.assertEqual(
            result["inspection_count"],
            len(expected_item_codes),
        )

        mock_update.assert_called_once()

        kwargs = mock_complete.call_args.kwargs

        self.assertEqual(
            kwargs["form_code"],
            TEST_POINT_DEFINITION.form_code,
        )

        self.assertEqual(
            kwargs["position_kind"],
            "point",
        )

        self.assertEqual(
            kwargs["expected_item_codes"],
            expected_item_codes,
        )

        self.assertEqual(
            kwargs["grade_options"],
            TEST_POINT_DEFINITION.grade_options,
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
                TEST_POINT_DEFINITION,
                survey_record_id=81,
                payload=(build_valid_point_payload()),
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

        payload = build_valid_point_payload()

        payload["record_data"]["design_flow"] = None

        with self.assertRaisesRegex(
            ValueError,
            "设计流量",
        ):
            complete_engineering_record(
                TEST_POINT_DEFINITION,
                survey_record_id=82,
                payload=payload,
            )

        mock_update.assert_not_called()
        mock_complete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
