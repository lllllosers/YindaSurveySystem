import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import database

from workflow_test_support import (
    EngineeringWorkflowTestCaseBase,
)

from services.tunnel_evaluation import (
    TUNNEL_EVALUATION_ITEMS,
)

from openpyxl import load_workbook

from services.tunnel_export import (
    export_tunnel_original_form,
    export_tunnel_summary,
)


class TunnelWorkflowTestCase(
    EngineeringWorkflowTestCaseBase,
):
    """
    附表2.5隧洞核心业务回归测试。
    """

    FORM_CODE = "form_2_5"

    TEST_DB_FILENAME = "test_tunnel.db"

    PROJECT_NAME = "附表2.5自动测试项目"
    PROJECT_SHORT_NAME = "2.5测试"

    BATCH_NAME = "附表2.5自动测试批次"
    BATCH_CODE = "FORM_2_5_TEST"

    BATCH_START_DATE = "2026-09-01"
    BATCH_END_DATE = "2026-12-31"

    DEPARTMENT_NAME = "测试基层处"
    DEPARTMENT_CODE = "01"

    OFFICE_NAME = "测试水管所"
    OFFICE_CODE = "01"

    CANAL_NAME = "测试总干渠"
    CANAL_LEVEL = "01"
    CANAL_DESCRIPTION = "自动测试"

    def test_export_tunnel_summary(
        self,
    ):
        record_data = self.make_complete_record_data()

        inspection_results = self.make_complete_inspection_results()

        database.create_range_engineering_survey(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            form_version_id=(self.form_version["id"]),
            asset_name=(record_data["asset_name"]),
            asset_type=(self.form_version["asset_type"]),
            organization_unit_id=(self.office_id),
            canal_unit_id=(self.canal_id),
            business_code=("1-01-01-05-001"),
            record_data=record_data,
            start_stake_text=(record_data["start_stake"]),
            start_stake_value=(record_data["start_stake_value"]),
            end_stake_text=(record_data["end_stake"]),
            end_stake_value=(record_data["end_stake_value"]),
            inspection_results=(inspection_results),
            survey_date="2026-09-14",
            overall_grade="A",
            survey_comment=("隧洞工程状况良好。"),
        )

        records = database.get_engineering_survey_query_records(
            project_id=(self.project_id),
            survey_batch_id=(self.batch_id),
            form_code="form_2_5",
        )

        output_path = self.temp_data_dir / "tunnel_summary.xlsx"

        result = export_tunnel_summary(
            records=records,
            file_path=output_path,
        )

        self.assertEqual(
            result["exported_count"],
            1,
        )

        self.assertTrue(output_path.exists())

        workbook = load_workbook(
            output_path,
            data_only=True,
        )

        worksheet = workbook["隧洞调查汇总"]

        self.assertEqual(
            worksheet["B2"].value,
            "1-01-01-05-001",
        )

        self.assertEqual(
            worksheet["C2"].value,
            "测试隧洞",
        )

        self.assertEqual(
            worksheet["G2"].value,
            "K20+000",
        )

        self.assertEqual(
            worksheet["H2"].value,
            "K21+200",
        )

        self.assertEqual(
            worksheet["U2"].value,
            "3.0*3.5",
        )

        # 第23列 W 开始为13项评价。
        self.assertEqual(
            worksheet["W2"].value,
            "A",
        )

        # 13项评价结束于 AI，
        # AJ 为工程状况类别。
        self.assertEqual(
            worksheet["AJ2"].value,
            "A",
        )

        workbook.close()

    def create_tunnel_draft(
        self,
        *,
        business_code="1-01-01-05-001",
        asset_name="测试隧洞",
        start_stake="K20+000",
        start_stake_value=20000.0,
        end_stake="K21+200",
        end_stake_value=21200.0,
        record_data=None,
        inspection_results=None,
        survey_date=None,
        overall_grade=None,
        survey_comment=None,
    ):
        if record_data is None:
            record_data = {
                "asset_name": asset_name,
                "start_stake": start_stake,
                "start_stake_value": start_stake_value,
                "end_stake": end_stake,
                "end_stake_value": end_stake_value,
                "design_flow": 8.5,
                "length": 1200.0,
            }

        return database.create_range_engineering_survey(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            form_version_id=self.form_version["id"],
            asset_name=asset_name,
            asset_type=self.form_version["asset_type"],
            organization_unit_id=self.office_id,
            canal_unit_id=self.canal_id,
            business_code=business_code,
            record_data=record_data,
            start_stake_text=start_stake,
            start_stake_value=start_stake_value,
            end_stake_text=end_stake,
            end_stake_value=end_stake_value,
            inspection_results=inspection_results,
            survey_date=survey_date,
            overall_grade=overall_grade,
            survey_comment=survey_comment,
        )

    def make_complete_record_data(
        self,
        *,
        asset_name="测试隧洞",
        start_stake="K20+000",
        start_stake_value=20000.0,
        end_stake="K21+200",
        end_stake_value=21200.0,
    ):
        return {
            "asset_name": asset_name,
            "start_stake": start_stake,
            "start_stake_value": start_stake_value,
            "end_stake": end_stake,
            "end_stake_value": end_stake_value,
            "design_flow": 8.5,
            "structure_grade": "3级",
            "build_date": "2010-06",
            "renovation_date": None,
            "length": 1200.0,
            "increased_flow": 10.0,
            "lining_form": "钢筋混凝土衬砌",
            "lining_thickness": 0.30,
            "concrete_strength": "C30",
            "inlet_outlet_bottom_elevation": "1680.25",
            "longitudinal_slope": 1.5,
            "section_form": "城门洞型",
            "section_width": 3.0,
            "section_height": 3.5,
            "cover_thickness": 0.05,
        }

    def make_complete_inspection_results(
        self,
        grade="A",
    ):
        return [
            {
                "item_code": item["item_code"],
                "category": item["category"],
                "item_name": item["item_name"],
                "grade": grade,
                "description": item["standards"][grade],
                "remark": None,
            }
            for item in TUNNEL_EVALUATION_ITEMS
        ]

    def test_form_2_5_definition_exists(self):
        form_version = self.form_version

        self.assertIsNotNone(form_version)

        self.assertEqual(
            form_version["form_code"],
            "form_2_5",
        )

        self.assertEqual(
            form_version["asset_type"],
            "tunnel",
        )

    def test_create_tunnel_range_draft(
        self,
    ):
        result = self.create_tunnel_draft()

        survey_record_id = int(result["survey_record_id"])

        engineering_asset_id = int(result["engineering_asset_id"])

        asset = database.get_engineering_asset_detail(engineering_asset_id)

        self.assertIsNotNone(asset)

        assert asset is not None

        self.assertEqual(
            asset["asset_type"],
            "tunnel",
        )

        # 范围工程不能写单桩号
        self.assertIsNone(asset["single_stake_text"])

        self.assertEqual(
            asset["start_stake_text"],
            "K20+000",
        )

        self.assertAlmostEqual(
            float(asset["start_stake_value"]),
            20000.0,
        )

        self.assertEqual(
            asset["end_stake_text"],
            "K21+200",
        )

        self.assertAlmostEqual(
            float(asset["end_stake_value"]),
            21200.0,
        )

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    record_type,
                    engineering_asset_id,
                    business_code,
                    record_status,
                    record_data_json
                FROM survey_records
                WHERE id = ?
                """,
                (survey_record_id,),
            ).fetchone()

        self.assertIsNotNone(row)

        assert row is not None

        self.assertEqual(
            row["record_type"],
            "engineering",
        )

        self.assertEqual(
            int(row["engineering_asset_id"]),
            engineering_asset_id,
        )

        self.assertEqual(
            row["record_status"],
            "draft",
        )

        record_data = json.loads(row["record_data_json"])

        self.assertEqual(
            record_data["design_flow"],
            8.5,
        )

        self.assertEqual(
            record_data["length"],
            1200.0,
        )

    def test_duplicate_tunnel_range_is_rejected(
        self,
    ):
        self.create_tunnel_draft(
            business_code="1-01-01-05-001",
        )

        with self.assertRaises(ValueError) as context:
            self.create_tunnel_draft(
                business_code="1-01-01-05-002",
                asset_name="另一个隧洞",
            )

        self.assertIn(
            "工程调查记录",
            str(context.exception),
        )

    def test_get_and_update_tunnel_record(
        self,
    ):
        result = self.create_tunnel_draft()

        survey_record_id = int(result["survey_record_id"])

        record = database.get_range_engineering_record(
            survey_record_id=survey_record_id,
            form_code="form_2_5",
        )

        self.assertIsNotNone(record)

        assert record is not None

        self.assertEqual(
            record["asset_type"],
            "tunnel",
        )

        self.assertEqual(
            record["start_stake_text"],
            "K20+000",
        )

        self.assertEqual(
            record["end_stake_text"],
            "K21+200",
        )

        updated_data = dict(record["record_data"])

        updated_data.update(
            {
                "asset_name": "修改后的隧洞",
                "design_flow": 9.2,
                "length": 1300.0,
            }
        )

        database.update_range_engineering_survey(
            survey_record_id=survey_record_id,
            form_code="form_2_5",
            asset_name="修改后的隧洞",
            record_data=updated_data,
            start_stake_text="K20+500",
            start_stake_value=20500.0,
            end_stake_text="K21+800",
            end_stake_value=21800.0,
        )

        updated_record = database.get_range_engineering_record(
            survey_record_id=survey_record_id,
            form_code="form_2_5",
        )

        self.assertIsNotNone(updated_record)

        assert updated_record is not None

        self.assertEqual(
            updated_record["asset_name"],
            "修改后的隧洞",
        )

        self.assertEqual(
            updated_record["start_stake_text"],
            "K20+500",
        )

        self.assertEqual(
            updated_record["end_stake_text"],
            "K21+800",
        )

        self.assertEqual(
            updated_record["record_data"]["design_flow"],
            9.2,
        )

        self.assertEqual(
            updated_record["record_data"]["length"],
            1300.0,
        )

    def test_tunnel_evaluation_configuration(
        self,
    ):
        self.assertEqual(
            len(TUNNEL_EVALUATION_ITEMS),
            13,
        )

        category_counts = {}

        for item in TUNNEL_EVALUATION_ITEMS:
            category = item["category"]

            category_counts[category] = (
                category_counts.get(
                    category,
                    0,
                )
                + 1
            )

        self.assertEqual(
            category_counts,
            {
                "水力条件": 4,
                "衬砌结构变形": 2,
                "衬砌结构破损": 4,
                "洞线地质": 3,
            },
        )

        item_codes = [item["item_code"] for item in TUNNEL_EVALUATION_ITEMS]

        self.assertEqual(
            len(item_codes),
            len(set(item_codes)),
        )

        for item in TUNNEL_EVALUATION_ITEMS:
            self.assertEqual(
                set(item["standards"].keys()),
                {
                    "A",
                    "B",
                    "C",
                    "D",
                },
            )

    def test_tunnel_evaluation_source_text(
        self,
    ):
        items = {item["item_name"]: item for item in TUNNEL_EVALUATION_ITEMS}

        self.assertEqual(
            items["进、出口流态"]["standards"]["A"],
            "进、出口及沿程流态平稳。",
        )

        self.assertEqual(
            items["进、出口流态"]["standards"]["D"],
            ("进、出口及沿程流态紊乱，" "出现连续、贯穿性漩涡。"),
        )

        self.assertEqual(
            items["过水流量"]["standards"]["C"],
            "过流能力为设计值的75%～90%。",
        )

        self.assertEqual(
            items["洞身围岩"]["standards"]["D"],
            ("洞身围岩破碎不稳定，" "变形和裂缝严重。"),
        )

        self.assertEqual(
            items["洞线地下水位"]["standards"]["D"],
            ("沿洞线地下水位高，" "排水失效，危及安全。"),
        )

    def test_tunnel_completion_requires_all_13_items(
        self,
    ):
        record_data = self.make_complete_record_data()

        result = self.create_tunnel_draft(
            record_data=record_data,
            survey_date="2026-09-14",
            overall_grade="A",
            survey_comment="自动测试调查意见",
        )

        survey_record_id = int(result["survey_record_id"])

        with self.assertRaises(ValueError) as context:
            database.complete_tunnel_record(survey_record_id)

        self.assertIn(
            "13",
            str(context.exception),
        )

    def test_complete_tunnel_record(
        self,
    ):
        record_data = self.make_complete_record_data()

        inspection_results = self.make_complete_inspection_results()

        result = self.create_tunnel_draft(
            record_data=record_data,
            inspection_results=inspection_results,
            survey_date="2026-09-14",
            overall_grade="A",
            survey_comment="自动测试调查意见",
        )

        survey_record_id = int(result["survey_record_id"])

        complete_result = database.complete_tunnel_record(survey_record_id)

        self.assertEqual(
            complete_result["inspection_count"],
            13,
        )

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT record_status
                FROM survey_records
                WHERE id = ?
                """,
                (survey_record_id,),
            ).fetchone()

        self.assertIsNotNone(row)

        assert row is not None

        self.assertEqual(
            row["record_status"],
            "completed",
        )

    def test_update_completed_tunnel_keeps_completed_status(
        self,
    ):
        record_data = self.make_complete_record_data()

        inspection_results = self.make_complete_inspection_results()

        result = self.create_tunnel_draft(
            record_data=record_data,
            inspection_results=inspection_results,
            survey_date="2026-09-14",
            overall_grade="A",
            survey_comment="自动测试调查意见",
        )

        survey_record_id = int(result["survey_record_id"])

        database.complete_tunnel_record(survey_record_id)

        record = database.get_range_engineering_record(
            survey_record_id=survey_record_id,
            form_code="form_2_5",
        )

        self.assertIsNotNone(record)

        assert record is not None

        updated_data = dict(record["record_data"])

        updated_data["design_flow"] = 9.5

        database.update_range_engineering_survey(
            survey_record_id=survey_record_id,
            form_code="form_2_5",
            asset_name=record["asset_name"],
            record_data=updated_data,
            start_stake_text=record["start_stake_text"],
            start_stake_value=record["start_stake_value"],
            end_stake_text=record["end_stake_text"],
            end_stake_value=record["end_stake_value"],
        )

        updated_record = database.get_range_engineering_record(
            survey_record_id=survey_record_id,
            form_code="form_2_5",
        )

        self.assertIsNotNone(updated_record)

        assert updated_record is not None

        self.assertEqual(
            updated_record["record_status"],
            "completed",
        )

        self.assertEqual(
            updated_record["record_data"]["design_flow"],
            9.5,
        )

    def test_export_tunnel_original_form(
        self,
    ):
        record_data = self.make_complete_record_data()

        inspection_results = self.make_complete_inspection_results()

        result = database.create_range_engineering_survey(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            form_version_id=(self.form_version["id"]),
            asset_name=(record_data["asset_name"]),
            asset_type=(self.form_version["asset_type"]),
            organization_unit_id=(self.office_id),
            canal_unit_id=(self.canal_id),
            business_code=("1-01-01-05-001"),
            record_data=record_data,
            start_stake_text=(record_data["start_stake"]),
            start_stake_value=(record_data["start_stake_value"]),
            end_stake_text=(record_data["end_stake"]),
            end_stake_value=(record_data["end_stake_value"]),
            inspection_results=(inspection_results),
            survey_date="2026-09-14",
            overall_grade="A",
            survey_comment=("隧洞工程状况良好。"),
        )

        survey_record_id = int(result["survey_record_id"])

        output_path = self.temp_data_dir / "tunnel_original.xlsx"

        export_tunnel_original_form(
            survey_record_id=(survey_record_id),
            file_path=output_path,
        )

        self.assertTrue(output_path.exists())

        workbook = load_workbook(
            output_path,
            data_only=True,
        )

        worksheet = workbook["附表2.5"]

        self.assertEqual(
            worksheet["B5"].value,
            "测试隧洞",
        )

        self.assertEqual(
            worksheet["F5"].value,
            "K20+000～K21+200",
        )

        self.assertEqual(
            worksheet["J5"].value,
            8.5,
        )

        self.assertEqual(
            worksheet["B7"].value,
            "钢筋混凝土衬砌",
        )

        self.assertEqual(
            worksheet["E8"].value,
            "3.0*3.5",
        )

        self.assertEqual(
            worksheet["E10"].value,
            "A",
        )

        self.assertEqual(
            worksheet["J23"].value,
            "A",
        )

        self.assertEqual(
            worksheet["J24"].value,
            "2026-09-14",
        )

        workbook.close()
