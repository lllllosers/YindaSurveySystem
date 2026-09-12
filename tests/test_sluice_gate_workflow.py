import gc
import time
import sys
import tempfile
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

from services.sluice_gate_evaluation import (
    SLUICE_GATE_EVALUATION_ITEMS,
)


class SluiceGateWorkflowTestCase(unittest.TestCase):
    """
    附表2.2水闸核心业务回归测试。

    每个测试均使用独立临时数据库，
    不接触正式 local_data/yinda_survey.db。
    """

    def setUp(self):
        # =========================
        # 临时测试数据库
        # =========================

        self.temp_directory = tempfile.TemporaryDirectory()

        self.temp_data_dir = Path(self.temp_directory.name) / "local_data"

        self.temp_db_path = self.temp_data_dir / "test_sluice_gate.db"

        self.original_data_dir = database.DATA_DIR

        self.original_db_path = database.DB_PATH

        database.DATA_DIR = self.temp_data_dir

        database.DB_PATH = self.temp_db_path

        database.init_database()
        database.create_initial_forms()

        # =========================
        # 建立一套完整测试上下文
        # =========================

        project_result = database.create_project(
            name="水闸自动测试项目",
            short_name="水闸测试",
        )

        self.project_id = int(project_result["project_id"])

        batch_result = database.create_survey_batch(
            project_id=self.project_id,
            batch_name="水闸自动测试批次",
            batch_code="SG_TEST_2026",
        )

        self.batch_id = int(batch_result["batch_id"])

        # -------------------------
        # 基层处
        # -------------------------

        department_id = database.create_organization_unit(
            name="测试基层处",
            unit_type="department",
            business_code="01",
        )

        self.assertIsNotNone(department_id)

        assert department_id is not None

        self.department_id = int(department_id)

        # -------------------------
        # 水管所
        # -------------------------

        office_id = database.create_organization_unit(
            name="测试水管所",
            unit_type="water_office",
            business_code="01",
            parent_id=self.department_id,
        )

        self.assertIsNotNone(office_id)

        assert office_id is not None

        self.office_id = int(office_id)

        # -------------------------
        # 渠系
        # -------------------------

        canal_id = database.create_canal_unit(
            name="测试干渠",
            canal_level="01",
            parent_id=None,
            organization_unit_id=(self.office_id),
            description="自动测试",
        )

        self.assertIsNotNone(canal_id)

        assert canal_id is not None

        self.canal_id = int(canal_id)

        # -------------------------
        # 附表2.2当前版本
        # -------------------------

        self.form_version = database.get_current_form_version("form_2_2")

        self.assertIsNotNone(self.form_version)

        assert self.form_version is not None

    def tearDown(self):
        database.DATA_DIR = self.original_data_dir

        database.DB_PATH = self.original_db_path

        gc.collect()
        time.sleep(0.05)

        self.temp_directory.cleanup()

    # =========================
    # 测试数据辅助
    # =========================

    def make_complete_record_data(
        self,
        *,
        asset_name="测试节制闸",
        stake="K1+000",
        stake_value=1000.0,
        design_flow=5.5,
    ):
        """
        构造满足附表2.2完成条件的基本信息。
        """

        return {
            "asset_name": asset_name,
            "stake": stake,
            "stake_value": stake_value,
            "design_flow": design_flow,
            "structure_grade": "3级",
            "build_date": "2010-06",
            "renovation_date": None,
            "opening_count": 2,
            "opening_width": 3.5,
            "opening_height": 2.8,
            "increased_flow": 6.5,
            "main_component_material": ("钢筋混凝土"),
            "concrete_strength": "C30",
            "reinforced_concrete_strength": ("C30"),
            "cover_thickness": 35.0,
            "crack_width_limit": 0.2,
        }

    def make_complete_inspection_results(
        self,
        grade="B",
    ):
        """
        根据正式评价配置自动生成14项评价。

        不在测试文件中手写14个 item_code，
        避免以后评价配置调整时测试数据失真。
        """

        results = []

        for item in SLUICE_GATE_EVALUATION_ITEMS:
            results.append(
                {
                    "item_code": (item["item_code"]),
                    "category": (item["category"]),
                    "item_name": (item["item_name"]),
                    "grade": grade,
                    "description": ("自动化测试情况描述"),
                    "remark": None,
                }
            )

        self.assertEqual(
            len(results),
            14,
        )

        return results

    def create_complete_draft(
        self,
        *,
        business_code="TEST-SG-001",
        asset_name="测试节制闸",
        stake="K1+000",
        stake_value=1000.0,
    ):
        """
        创建一条内容完整、但状态仍为 draft 的
        附表2.2调查记录。
        """

        record_data = self.make_complete_record_data(
            asset_name=asset_name,
            stake=stake,
            stake_value=stake_value,
        )

        inspection_results = self.make_complete_inspection_results()

        result = database.create_engineering_survey(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            form_version_id=(self.form_version["id"]),
            asset_name=asset_name,
            asset_type=(self.form_version["asset_type"]),
            organization_unit_id=(self.office_id),
            canal_unit_id=(self.canal_id),
            business_code=business_code,
            record_data=record_data,
            single_stake_text=stake,
            single_stake_value=(stake_value),
            inspection_results=(inspection_results),
            survey_date="2026-09-12",
            overall_grade="B",
            survey_comment=("自动化测试调查意见。"),
        )

        return result

    # =========================
    # 测试1
    # 完整草稿能够正确保存
    # =========================

    def test_create_sluice_gate_draft(
        self,
    ):
        result = self.create_complete_draft()

        survey_record_id = int(result["survey_record_id"])

        engineering_asset_id = int(result["engineering_asset_id"])

        record = database.get_sluice_gate_record(survey_record_id)

        self.assertIsNotNone(record)

        assert record is not None

        self.assertEqual(
            record["record_status"],
            "draft",
        )

        self.assertEqual(
            record["asset_name"],
            "测试节制闸",
        )

        self.assertEqual(
            record["business_code"],
            "TEST-SG-001",
        )

        self.assertEqual(
            int(record["engineering_asset_id"]),
            engineering_asset_id,
        )

        self.assertEqual(
            record["record_data"]["design_flow"],
            5.5,
        )

        inspections = database.get_inspection_results(survey_record_id)

        self.assertEqual(
            len(inspections),
            14,
        )

    # =========================
    # 测试2
    # 必须14项全部评价才能完成
    # =========================

    def test_completion_requires_all_14_items(
        self,
    ):
        record_data = self.make_complete_record_data()

        inspection_results = self.make_complete_inspection_results()

        # 故意少一项。
        inspection_results = inspection_results[:-1]

        result = database.create_engineering_survey(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            form_version_id=(self.form_version["id"]),
            asset_name="不完整评价水闸",
            asset_type=(self.form_version["asset_type"]),
            organization_unit_id=(self.office_id),
            canal_unit_id=(self.canal_id),
            business_code=("TEST-SG-INCOMPLETE"),
            record_data=record_data,
            single_stake_text="K2+000",
            single_stake_value=2000.0,
            inspection_results=(inspection_results),
            survey_date="2026-09-12",
            overall_grade="B",
            survey_comment=("自动化测试调查意见。"),
        )

        survey_record_id = int(result["survey_record_id"])

        with self.assertRaises(ValueError):
            database.complete_sluice_gate_record(survey_record_id)

        record = database.get_sluice_gate_record(survey_record_id)

        self.assertIsNotNone(record)

        assert record is not None

        # 完成失败后仍必须是草稿。
        self.assertEqual(
            record["record_status"],
            "draft",
        )

    # =========================
    # 测试3
    # 草稿 → 完成 → 已完成直接修改
    # =========================

    def test_complete_then_edit_completed_record(
        self,
    ):
        result = self.create_complete_draft()

        survey_record_id = int(result["survey_record_id"])

        complete_result = database.complete_sluice_gate_record(survey_record_id)

        self.assertEqual(
            int(complete_result["survey_record_id"]),
            survey_record_id,
        )

        record = database.get_sluice_gate_record(survey_record_id)

        self.assertIsNotNone(record)

        assert record is not None

        self.assertEqual(
            record["record_status"],
            "completed",
        )

        # -------------------------
        # 修改已完成记录
        # -------------------------

        updated_data = self.make_complete_record_data(
            asset_name=("修改后的测试节制闸"),
            design_flow=8.8,
        )

        database.update_sluice_gate_draft(
            survey_record_id=(survey_record_id),
            asset_name=("修改后的测试节制闸"),
            record_data=updated_data,
            single_stake_text="K1+000",
            single_stake_value=1000.0,
            inspection_results=(self.make_complete_inspection_results(grade="A")),
            survey_date="2026-09-13",
            overall_grade="A",
            survey_comment=("已完成记录修改测试。"),
        )

        updated_record = database.get_sluice_gate_record(survey_record_id)

        self.assertIsNotNone(updated_record)

        assert updated_record is not None

        # 修改后状态不能退回 draft。
        self.assertEqual(
            updated_record["record_status"],
            "completed",
        )

        self.assertEqual(
            updated_record["asset_name"],
            "修改后的测试节制闸",
        )

        self.assertEqual(
            updated_record["record_data"]["design_flow"],
            8.8,
        )

        self.assertEqual(
            updated_record["overall_grade"],
            "A",
        )

        inspections = database.get_inspection_results(survey_record_id)

        self.assertEqual(
            len(inspections),
            14,
        )

        self.assertTrue(all(row["grade"] == "A" for row in inspections))

    # =========================
    # 测试4
    # 同批次同工程重复保护
    # =========================

    def test_duplicate_sluice_gate_is_rejected(
        self,
    ):
        self.create_complete_draft(
            business_code="TEST-SG-001",
            stake="K3+500",
            stake_value=3500.0,
        )

        # 同：
        # 项目
        # 批次
        # 表单
        # 水管所
        # 渠系
        # 标准化桩号
        #
        # 即使工程名和业务编号不同，
        # 仍应判断为同一工程调查。
        with self.assertRaises(ValueError):
            self.create_complete_draft(
                business_code=("TEST-SG-002"),
                asset_name=("另一个工程名称"),
                stake="K3+500",
                stake_value=3500.0,
            )

    # =========================
    # 测试5
    # 删除调查同时清理评价和孤立工程
    # =========================

    def test_delete_record_cleans_orphan_asset(
        self,
    ):
        result = self.create_complete_draft()

        survey_record_id = int(result["survey_record_id"])

        engineering_asset_id = int(result["engineering_asset_id"])

        database.delete_sluice_gate_record(survey_record_id)

        # -------------------------
        # 调查记录已删除
        # -------------------------

        record = database.get_sluice_gate_record(survey_record_id)

        self.assertIsNone(record)

        # -------------------------
        # inspection_results
        # 应由外键级联删除
        # -------------------------

        inspections = database.get_inspection_results(survey_record_id)

        self.assertEqual(
            len(inspections),
            0,
        )

        # -------------------------
        # 没有其它调查记录后，
        # EngineeringAsset 也应清理
        # -------------------------

        with database.get_connection() as connection:
            asset = connection.execute(
                """
                SELECT id
                FROM engineering_assets
                WHERE id = ?
                """,
                (engineering_asset_id,),
            ).fetchone()

        self.assertIsNone(asset)


if __name__ == "__main__":
    unittest.main()
