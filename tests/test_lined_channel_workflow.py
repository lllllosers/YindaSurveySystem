import gc
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

# =========================
# 让测试可以导入 src
# =========================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


import database


class LinedChannelWorkflowTestCase(unittest.TestCase):
    """
    附表2.1防渗衬砌渠道渠段
    V0.3.0-A1 最小持久化测试。

    每个测试使用独立临时 SQLite 数据库，
    不接触正式数据库。
    """

    def setUp(self):
        # =========================
        # 独立临时数据库
        # =========================

        self.temp_directory = tempfile.TemporaryDirectory()

        self.temp_data_dir = Path(self.temp_directory.name) / "local_data"

        self.temp_db_path = self.temp_data_dir / "test_yinda_survey.db"

        self.original_data_dir = database.DATA_DIR
        self.original_db_path = database.DB_PATH

        database.DATA_DIR = self.temp_data_dir
        database.DB_PATH = self.temp_db_path

        database.init_database()
        database.create_initial_forms()

        # =========================
        # 建立最小业务环境
        # =========================

        project_result = database.create_project(
            name="附表2.1自动测试项目",
            short_name="2.1测试",
        )

        self.project_id = int(project_result["project_id"])

        batch_result = database.create_survey_batch(
            project_id=self.project_id,
            batch_name="附表2.1自动测试批次",
            batch_code="FORM_2_1_TEST",
            start_date="2026-09-01",
            end_date="2026-12-31",
        )

        self.batch_id = int(batch_result["batch_id"])

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
            organization_unit_id=self.office_id,
        )

    def tearDown(self):
        database.DATA_DIR = self.original_data_dir
        database.DB_PATH = self.original_db_path

        gc.collect()
        time.sleep(0.05)

        self.temp_directory.cleanup()

    # =========================
    # 测试1：
    # 附表2.1元数据正确存在
    # =========================

    def test_form_2_1_definition_exists(self):
        form_version = database.get_current_form_version("form_2_1")

        self.assertIsNotNone(form_version)

        assert form_version is not None

        self.assertEqual(
            form_version["form_number"],
            "2.1",
        )

        self.assertEqual(
            form_version["asset_type"],
            "lined_channel_section",
        )

    # =========================
    # 测试2：
    # 渠段型 EngineeringAsset
    # 正确保存起止桩号
    # =========================

    def test_create_lined_channel_section_survey(
        self,
    ):
        form_version = database.get_current_form_version("form_2_1")

        self.assertIsNotNone(form_version)

        assert form_version is not None

        result = database.create_lined_channel_section_survey(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            form_version_id=form_version["id"],
            asset_name="测试总干渠",
            organization_unit_id=self.office_id,
            canal_unit_id=self.canal_id,
            business_code=("1-01-01-01-001"),
            record_data={
                "channel_name": "测试总干渠",
                "section_length": 1250.0,
            },
            start_stake_text="K12+000",
            start_stake_value=12000.0,
            end_stake_text="K13+250",
            end_stake_value=13250.0,
        )

        engineering_asset_id = int(result["engineering_asset_id"])

        survey_record_id = int(result["survey_record_id"])

        # -------------------------
        # 1. 检查 EngineeringAsset
        # -------------------------

        asset = database.get_engineering_asset_detail(engineering_asset_id)

        self.assertIsNotNone(asset)

        assert asset is not None

        self.assertEqual(
            asset["asset_type"],
            "lined_channel_section",
        )

        # 渠段型工程不能写入单桩号
        self.assertIsNone(asset["single_stake_text"])

        self.assertEqual(
            asset["start_stake_text"],
            "K12+000",
        )

        self.assertEqual(
            float(asset["start_stake_value"]),
            12000.0,
        )

        self.assertEqual(
            asset["end_stake_text"],
            "K13+250",
        )

        self.assertEqual(
            float(asset["end_stake_value"]),
            13250.0,
        )

        # -------------------------
        # 2. 检查 SurveyRecord
        # -------------------------

        with database.get_connection() as connection:
            record = connection.execute(
                """
                SELECT
                    project_id,
                    survey_batch_id,
                    form_version_id,
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

        self.assertIsNotNone(record)

        assert record is not None

        self.assertEqual(
            int(record["project_id"]),
            self.project_id,
        )

        self.assertEqual(
            int(record["survey_batch_id"]),
            self.batch_id,
        )

        self.assertEqual(
            int(record["form_version_id"]),
            int(form_version["id"]),
        )

        self.assertEqual(
            int(record["engineering_asset_id"]),
            engineering_asset_id,
        )

        self.assertEqual(
            record["record_type"],
            "engineering",
        )

        self.assertEqual(
            record["record_status"],
            "draft",
        )

        self.assertEqual(
            record["business_code"],
            "1-01-01-01-001",
        )

        record_data = json.loads(record["record_data_json"])

        self.assertEqual(
            record_data["channel_name"],
            "测试总干渠",
        )

        self.assertEqual(
            record_data["section_length"],
            1250.0,
        )

        # -------------------------
        # 3. 检查现有工程台账查询
        # -------------------------

        assets = database.get_engineering_assets(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
        )

        self.assertEqual(
            len(assets),
            1,
        )

        ledger_asset = assets[0]

        self.assertEqual(
            ledger_asset["start_stake_text"],
            "K12+000",
        )

        self.assertEqual(
            ledger_asset["end_stake_text"],
            "K13+250",
        )

        self.assertIsNone(ledger_asset["single_stake_text"])

    def test_lined_channel_record_can_be_loaded(
        self,
    ):
        form_version = database.get_current_form_version("form_2_1")

        result = database.create_lined_channel_section_survey(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            form_version_id=form_version["id"],
            asset_name="测试总干渠",
            organization_unit_id=self.office_id,
            canal_unit_id=self.canal_id,
            business_code=("1-01-01-01-001"),
            record_data={
                "channel_name": "测试总干渠",
                "section_length": 1250.0,
                "build_date": "2008-06",
            },
            start_stake_text="K12+000",
            start_stake_value=12000.0,
            end_stake_text="K13+250",
            end_stake_value=13250.0,
        )

        record = database.get_lined_channel_section_record(result["survey_record_id"])

        self.assertEqual(
            record["asset_name"],
            "测试总干渠",
        )

        self.assertEqual(
            record["asset_type"],
            "lined_channel_section",
        )

        self.assertEqual(
            record["start_stake_text"],
            "K12+000",
        )

        self.assertEqual(
            record["end_stake_text"],
            "K13+250",
        )

        self.assertEqual(
            record["record_status"],
            "draft",
        )

        self.assertEqual(
            record["record_data"]["build_date"],
            "2008-06",
        )

    def test_lined_channel_draft_can_be_updated(
        self,
    ):
        form_version = database.get_current_form_version("form_2_1")

        result = database.create_lined_channel_section_survey(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            form_version_id=form_version["id"],
            asset_name="测试总干渠",
            organization_unit_id=self.office_id,
            canal_unit_id=self.canal_id,
            business_code=("1-01-01-01-001"),
            record_data={
                "channel_name": "测试总干渠",
                "section_length": 1250.0,
            },
            start_stake_text="K12+000",
            start_stake_value=12000.0,
            end_stake_text="K13+250",
            end_stake_value=13250.0,
        )

        survey_record_id = result["survey_record_id"]

        engineering_asset_id = result["engineering_asset_id"]

        database.update_lined_channel_section_draft(
            survey_record_id=survey_record_id,
            asset_name="测试总干渠修改后",
            organization_unit_id=self.office_id,
            canal_unit_id=self.canal_id,
            business_code=("1-01-01-01-001"),
            record_data={
                "channel_name": ("测试总干渠修改后"),
                "section_length": 1500.0,
                "build_date": "2010-08",
            },
            start_stake_text="K12+100",
            start_stake_value=12100.0,
            end_stake_text="K13+600",
            end_stake_value=13600.0,
        )

        record = database.get_lined_channel_section_record(survey_record_id)

        # 仍然是原来的 EngineeringAsset
        self.assertEqual(
            record["engineering_asset_id"],
            engineering_asset_id,
        )

        # 仍然是原来的 SurveyRecord
        self.assertEqual(
            record["survey_record_id"],
            survey_record_id,
        )

        self.assertEqual(
            record["asset_name"],
            "测试总干渠修改后",
        )

        self.assertEqual(
            record["start_stake_text"],
            "K12+100",
        )

        self.assertEqual(
            record["end_stake_text"],
            "K13+600",
        )

        self.assertIsNone(record["single_stake_text"])

        self.assertEqual(
            record["record_data"]["section_length"],
            1500.0,
        )

        self.assertEqual(
            record["record_data"]["build_date"],
            "2010-08",
        )

        records = database.get_lined_channel_section_records(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
        )

        self.assertEqual(
            len(records),
            1,
        )

        self.assertEqual(
            records[0]["survey_record_id"],
            survey_record_id,
        )

        self.assertEqual(
            records[0]["start_stake_text"],
            "K12+100",
        )

        self.assertEqual(
            records[0]["end_stake_text"],
            "K13+600",
        )

    def test_all_basic_fields_round_trip(
        self,
    ):
        form_version = database.get_current_form_version("form_2_1")

        record_data = {
            "channel_name": "测试一干渠",
            "start_stake": "K10+000",
            "start_stake_value": 10000.0,
            "end_stake": "K11+500",
            "end_stake_value": 11500.0,
            "section_length": 1500.0,
            "build_date": "2008-06",
            "renovation_date": "2021-09",
            "longitudinal_slope": "1/2000",
            "design_flow": 12.5,
            "channel_grade": "3级",
            "cross_section_form": "梯形",
            "embankment_top_width": 3.5,
            "inner_slope": "1:1.5",
            "outer_slope": "1:1.5",
            "increased_flow": 15.0,
            "bed_soil": "砂壤土",
            "lining_structure": ("现浇混凝土衬砌"),
            "freeboard": 0.6,
            "bottom_width": 4.2,
            "water_conveyance_loss": 0.08,
            "lining_material": "混凝土",
            "lining_thickness": 12.0,
            "concrete_strength": "C25",
            "channel_depth": 2.8,
            "channel_bottom_elevation": (1865.35),
        }

        result = database.create_lined_channel_section_survey(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            form_version_id=(form_version["id"]),
            asset_name="测试一干渠",
            organization_unit_id=(self.office_id),
            canal_unit_id=self.canal_id,
            business_code=("1-01-01-01-001"),
            record_data=record_data,
            start_stake_text="K10+000",
            start_stake_value=10000.0,
            end_stake_text="K11+500",
            end_stake_value=11500.0,
        )

        loaded = database.get_lined_channel_section_record(result["survey_record_id"])

        loaded_data = loaded["record_data"]

        self.assertEqual(
            loaded["start_stake_text"],
            "K10+000",
        )

        self.assertEqual(
            loaded["end_stake_text"],
            "K11+500",
        )

        for key, expected_value in record_data.items():
            self.assertEqual(
                loaded_data[key],
                expected_value,
                msg=f"字段回填失败：{key}",
            )


if __name__ == "__main__":
    unittest.main()
