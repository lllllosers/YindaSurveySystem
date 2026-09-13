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


if __name__ == "__main__":
    unittest.main()
