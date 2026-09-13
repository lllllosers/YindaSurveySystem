import gc
import sys
import tempfile
import time
import unittest
from pathlib import Path

from openpyxl import load_workbook

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


import database

from services.query_export import (
    export_common_query_summary,
)


class DataQueryTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()

        self.temp_data_dir = Path(self.temp_directory.name) / "local_data"

        self.temp_db_path = self.temp_data_dir / "test_data_query.db"

        self.original_data_dir = database.DATA_DIR

        self.original_db_path = database.DB_PATH

        database.DATA_DIR = self.temp_data_dir

        database.DB_PATH = self.temp_db_path

        database.init_database()
        database.create_initial_forms()

        # =====================================================
        # 项目
        # =====================================================

        project_result = database.create_project(
            name="统一数据查询测试项目",
            short_name="查询测试",
        )

        self.project_id = int(project_result["project_id"])

        # =====================================================
        # 两个调查批次
        # =====================================================

        batch_1 = database.create_survey_batch(
            project_id=(self.project_id),
            batch_name=("2026年度调查"),
            batch_code=("QUERY_2026"),
            start_date=("2026-09-01"),
            end_date=("2026-12-31"),
        )

        self.batch_1_id = int(batch_1["batch_id"])

        batch_2 = database.create_survey_batch(
            project_id=(self.project_id),
            batch_name=("2027年度调查"),
            batch_code=("QUERY_2027"),
            start_date=("2027-09-01"),
            end_date=("2027-12-31"),
        )

        self.batch_2_id = int(batch_2["batch_id"])

        # =====================================================
        # 机构 / 渠系
        # =====================================================

        department_id = database.create_organization_unit(
            name="测试基层处",
            unit_type="department",
            business_code="1",
        )

        self.office_id = database.create_organization_unit(
            name="测试水管所",
            unit_type="water_office",
            business_code="01",
            parent_id=department_id,
        )

        self.canal_id = database.create_canal_unit(
            name="测试总干渠",
            canal_level="01",
            organization_unit_id=(self.office_id),
        )

        # =====================================================
        # 附表2.1：2026
        # =====================================================

        form_2_1 = database.get_current_form_version("form_2_1")

        database.create_lined_channel_section_survey(
            project_id=self.project_id,
            survey_batch_id=(self.batch_1_id),
            form_version_id=(form_2_1["id"]),
            asset_name="测试渠段A",
            organization_unit_id=(self.office_id),
            canal_unit_id=(self.canal_id),
            business_code=("1-01-01-01-001"),
            record_data={
                "channel_name": ("测试渠段A"),
                "section_length": (1000.0),
            },
            start_stake_text=("K10+000"),
            start_stake_value=(10000.0),
            end_stake_text=("K11+000"),
            end_stake_value=(11000.0),
            survey_date=("2026-09-13"),
            overall_grade="B",
            survey_comment=("测试意见A"),
        )

        # =====================================================
        # 附表2.2：2026
        # =====================================================

        form_2_2 = database.get_current_form_version("form_2_2")

        database.create_engineering_survey(
            project_id=self.project_id,
            survey_batch_id=(self.batch_1_id),
            form_version_id=(form_2_2["id"]),
            asset_name="测试水闸A",
            asset_type="sluice_gate",
            organization_unit_id=(self.office_id),
            canal_unit_id=(self.canal_id),
            business_code=("1-01-01-02-001"),
            record_data={
                "stake": "K20+500",
                "design_flow": 10.0,
            },
            single_stake_text=("K20+500"),
            single_stake_value=(20500.0),
            survey_date=("2026-09-14"),
            overall_grade="C",
            survey_comment=("测试意见B"),
        )

        # =====================================================
        # 附表2.1：2027
        # =====================================================

        database.create_lined_channel_section_survey(
            project_id=self.project_id,
            survey_batch_id=(self.batch_2_id),
            form_version_id=(form_2_1["id"]),
            asset_name="测试渠段B",
            organization_unit_id=(self.office_id),
            canal_unit_id=(self.canal_id),
            business_code=("1-01-01-01-002"),
            record_data={
                "channel_name": ("测试渠段B"),
                "section_length": (500.0),
            },
            start_stake_text=("K30+000"),
            start_stake_value=(30000.0),
            end_stake_text=("K30+500"),
            end_stake_value=(30500.0),
            survey_date=("2027-09-13"),
            overall_grade="A",
            survey_comment=("测试意见C"),
        )

    def tearDown(self):
        database.DATA_DIR = self.original_data_dir

        database.DB_PATH = self.original_db_path

        gc.collect()
        time.sleep(0.05)

        self.temp_directory.cleanup()

    # =========================================================
    # 测试1：两个表统一查询
    # =========================================================

    def test_query_returns_multiple_forms(
        self,
    ):
        records = database.get_engineering_survey_query_records(
            project_id=(self.project_id)
        )

        self.assertEqual(
            len(records),
            3,
        )

        form_codes = {record["form_code"] for record in records}

        self.assertEqual(
            form_codes,
            {
                "form_2_1",
                "form_2_2",
            },
        )

        lined_record = next(
            record for record in records if record["asset_name"] == "测试渠段A"
        )

        self.assertEqual(
            lined_record["engineering_position"],
            "K10+000 ～ K11+000",
        )

        sluice_record = next(
            record for record in records if record["asset_name"] == "测试水闸A"
        )

        self.assertEqual(
            sluice_record["engineering_position"],
            "K20+500",
        )

    # =========================================================
    # 测试2：数据库层按批次 / 表单过滤
    # =========================================================

    def test_query_filters_batch_and_form(
        self,
    ):
        batch_records = database.get_engineering_survey_query_records(
            project_id=(self.project_id),
            survey_batch_id=(self.batch_1_id),
        )

        self.assertEqual(
            len(batch_records),
            2,
        )

        form_records = database.get_engineering_survey_query_records(
            project_id=(self.project_id),
            form_code="form_2_1",
        )

        self.assertEqual(
            len(form_records),
            2,
        )

        combined_records = database.get_engineering_survey_query_records(
            project_id=(self.project_id),
            survey_batch_id=(self.batch_1_id),
            form_code="form_2_2",
        )

        self.assertEqual(
            len(combined_records),
            1,
        )

        self.assertEqual(
            combined_records[0]["asset_name"],
            "测试水闸A",
        )

    # =========================================================
    # 测试3：跨表公共结果导出
    # =========================================================

    def test_export_common_query_summary(
        self,
    ):
        records = database.get_engineering_survey_query_records(
            project_id=(self.project_id)
        )

        file_path = Path(self.temp_directory.name) / "query_summary.xlsx"

        result = export_common_query_summary(
            records=records,
            file_path=file_path,
        )

        self.assertEqual(
            result["exported_count"],
            3,
        )

        self.assertTrue(file_path.exists())

        workbook = load_workbook(file_path)

        worksheet = workbook["统一数据查询"]

        self.assertEqual(
            worksheet["A1"].value,
            "序号",
        )

        self.assertEqual(
            worksheet["B1"].value,
            "调查表",
        )

        self.assertEqual(
            worksheet["I1"].value,
            "工程位置",
        )

        exported_names = {
            worksheet.cell(
                row=row,
                column=5,
            ).value
            for row in range(
                2,
                worksheet.max_row + 1,
            )
        }

        self.assertCountEqual(
            exported_names,
            [
                "测试渠段A",
                "测试水闸A",
                "测试渠段B",
            ],
        )

        self.assertEqual(
            exported_names,
            {
                "测试渠段A",
                "测试水闸A",
                "测试渠段B",
            },
        )

        workbook.close()


if __name__ == "__main__":
    unittest.main()
