import json
import sys
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

from tests.workflow_test_support import (
    EngineeringWorkflowTestCaseBase,
)

from openpyxl import (
    load_workbook,
)

from services.aqueduct_evaluation import (
    AQUEDUCT_EVALUATION_ITEMS,
)

from services.business_code import (
    build_business_code,
    get_engineering_type_code,
)

from services.aqueduct_export import (
    export_aqueduct_original_form,
)


class AqueductWorkflowTestCase(
    EngineeringWorkflowTestCaseBase,
):
    """
    附表2.3渡槽（座槽）核心业务回归测试。

    当前第一阶段先验证：
    1. 表单元数据；
    2. 工程类型码和业务编号。

    每个测试使用独立临时 SQLite 数据库，
    不接触正式 local_data/yinda_survey.db。
    """

    FORM_CODE = "form_2_3"

    TEST_DB_FILENAME = "test_aqueduct.db"

    PROJECT_NAME = "渡槽自动测试项目"
    PROJECT_SHORT_NAME = "渡槽测试"

    BATCH_NAME = "渡槽自动测试批次"
    BATCH_CODE = "AQ_TEST_2026"

    DEPARTMENT_NAME = "测试基层处"
    DEPARTMENT_CODE = "01"

    OFFICE_NAME = "测试水管所"
    OFFICE_CODE = "01"

    CANAL_NAME = "测试干渠"
    CANAL_LEVEL = "01"
    CANAL_DESCRIPTION = "自动测试"

    # =========================
    # 测试数据辅助
    # =========================

    def create_aqueduct_draft(
        self,
        *,
        business_code="TEST-AQ-001",
        asset_name="测试渡槽",
        stake="K1+250",
        stake_value=1250.0,
    ):
        """
        使用公共点状工程创建能力，
        创建一条附表2.3渡槽草稿。
        """

        record_data = {
            "asset_name": asset_name,
            "stake": stake,
            "stake_value": stake_value,
            "design_flow": 4.5,
            "length": 120.0,
        }

        return database.create_engineering_survey(
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
        )

    def make_complete_record_data(
        self,
        *,
        asset_name="测试渡槽",
        stake="K1+250",
        stake_value=1250.0,
    ):
        """
        构造满足附表2.3完成条件的
        全部正式基本信息。
        """

        return {
            "asset_name": asset_name,
            "stake": stake,
            "stake_value": stake_value,
            "design_flow": 4.5,
            "structure_grade": "3级",
            "build_date": "2010-06",
            "renovation_date": None,
            "length": 120.0,
            "increased_flow": 5.5,
            "structure_form": "梁式渡槽",
            "section_width": 3.2,
            "section_height": 2.4,
            "trough_body_structure": ("钢筋混凝土"),
            "trough_wall_thickness": 0.25,
            "waterstop_form": "橡胶止水",
            "trough_bottom_elevation": (1685.35),
            "span_count": 6,
            "lower_support_structure_form": ("排架式"),
        }

    def make_complete_inspection_results(
        self,
        grade="B",
    ):
        """
        根据正式附表2.3评价配置
        自动生成完整12项评价。
        """

        results = []

        for item in AQUEDUCT_EVALUATION_ITEMS:
            results.append(
                {
                    "item_code": (item["item_code"]),
                    "category": (item["category"]),
                    "item_name": (item["item_name"]),
                    "grade": grade,
                    "description": None,
                    "remark": None,
                }
            )

        self.assertEqual(
            len(results),
            12,
        )

        return results

    # =========================
    # 测试1：
    # 附表2.3元数据正确存在
    # =========================

    def test_form_2_3_definition_exists(self):
        form_version = database.get_current_form_version("form_2_3")

        self.assertIsNotNone(form_version)

        assert form_version is not None

        self.assertEqual(
            form_version["form_number"],
            "2.3",
        )

        self.assertEqual(
            form_version["form_name"],
            "渡槽（座槽）工程状况调查表",
        )

        self.assertEqual(
            form_version["asset_type"],
            "aqueduct",
        )

    # =========================
    # 测试2：
    # 附表2.3工程类型码为03
    # =========================

    def test_aqueduct_business_code_uses_type_03(self):
        engineering_type_code = get_engineering_type_code("form_2_3")

        self.assertEqual(
            engineering_type_code,
            "03",
        )

        business_code = build_business_code(
            department_code="1",
            water_office_code="01",
            canal_level_code="03",
            engineering_type_code=(engineering_type_code),
            sequence=1,
        )

        self.assertEqual(
            business_code,
            "1-01-03-03-001",
        )

    # =========================
    # 测试3：
    # 渡槽复用公共点状工程创建能力
    # =========================

    def test_create_aqueduct_point_draft(
        self,
    ):
        result = self.create_aqueduct_draft()

        survey_record_id = int(result["survey_record_id"])

        engineering_asset_id = int(result["engineering_asset_id"])

        # -------------------------
        # 通用工程调查查询
        # 应能够直接查询到附表2.3
        # -------------------------

        records = database.get_engineering_survey_query_records(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            form_code="form_2_3",
        )

        self.assertEqual(
            len(records),
            1,
        )

        record = records[0]

        self.assertEqual(
            int(record["survey_record_id"]),
            survey_record_id,
        )

        self.assertEqual(
            int(record["engineering_asset_id"]),
            engineering_asset_id,
        )

        self.assertEqual(
            record["form_code"],
            "form_2_3",
        )

        self.assertEqual(
            record["asset_type"],
            "aqueduct",
        )

        self.assertEqual(
            record["asset_name"],
            "测试渡槽",
        )

        self.assertEqual(
            record["engineering_position"],
            "K1+250",
        )

        self.assertEqual(
            record["record_status"],
            "draft",
        )

        # -------------------------
        # 底层工程对象必须是单桩号工程
        # 起止桩号必须保持为空
        # -------------------------

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    ea.asset_type,
                    ea.single_stake_text,
                    ea.single_stake_value,
                    ea.start_stake_text,
                    ea.start_stake_value,
                    ea.end_stake_text,
                    ea.end_stake_value,
                    sr.record_data_json
                FROM survey_records AS sr
                JOIN engineering_assets AS ea
                    ON sr.engineering_asset_id = ea.id
                WHERE sr.id = ?
                """,
                (survey_record_id,),
            ).fetchone()

        self.assertIsNotNone(row)

        assert row is not None

        self.assertEqual(
            row["asset_type"],
            "aqueduct",
        )

        self.assertEqual(
            row["single_stake_text"],
            "K1+250",
        )

        self.assertAlmostEqual(
            float(row["single_stake_value"]),
            1250.0,
        )

        self.assertIsNone(row["start_stake_text"])

        self.assertIsNone(row["start_stake_value"])

        self.assertIsNone(row["end_stake_text"])

        self.assertIsNone(row["end_stake_value"])

        record_data = json.loads(row["record_data_json"])

        self.assertEqual(
            record_data["asset_name"],
            "测试渡槽",
        )

        self.assertEqual(
            record_data["design_flow"],
            4.5,
        )

        self.assertEqual(
            record_data["length"],
            120.0,
        )

    # =========================
    # 测试4：
    # 渡槽复用公共点状工程重复保护
    # =========================

    def test_duplicate_aqueduct_is_rejected(
        self,
    ):
        self.create_aqueduct_draft(
            business_code="TEST-AQ-001",
            asset_name="测试渡槽一",
            stake="K3+500",
            stake_value=3500.0,
        )

        # 同一：
        # 项目
        # 批次
        # 表单
        # 水管所
        # 渠系
        # 标准化桩号
        #
        # 即使名称和业务编号不同，
        # 仍属于重复调查。

        with self.assertRaises(ValueError) as context:
            self.create_aqueduct_draft(
                business_code=("TEST-AQ-002"),
                asset_name=("另一个渡槽名称"),
                stake="K3+500",
                stake_value=3500.0,
            )

        message = str(context.exception)

        self.assertIn(
            "工程调查记录",
            message,
        )

        # 公共函数不能再泄漏
        # 附表2.2专属“水闸”文案。
        self.assertNotIn(
            "水闸调查记录",
            message,
        )

    # =========================
    # 测试5：
    # 渡槽复用公共点状工程读取和修改
    # =========================

    def test_get_and_update_aqueduct_record(
        self,
    ):
        result = self.create_aqueduct_draft()

        survey_record_id = int(result["survey_record_id"])

        # -------------------------
        # 公共读取
        # -------------------------

        record = database.get_point_engineering_record(
            survey_record_id=(survey_record_id),
            form_code="form_2_3",
        )

        self.assertIsNotNone(record)

        assert record is not None

        self.assertEqual(
            record["form_code"],
            "form_2_3",
        )

        self.assertEqual(
            record["asset_type"],
            "aqueduct",
        )

        self.assertEqual(
            record["asset_name"],
            "测试渡槽",
        )

        self.assertEqual(
            record["single_stake_text"],
            "K1+250",
        )

        # -------------------------
        # 公共修改
        # -------------------------

        updated_data = dict(record["record_data"])

        updated_data.update(
            {
                "asset_name": ("修改后的测试渡槽"),
                "stake": "K1+500",
                "stake_value": 1500.0,
                "design_flow": 8.8,
                "length": 180.0,
            }
        )

        database.update_point_engineering_survey(
            survey_record_id=(survey_record_id),
            form_code="form_2_3",
            asset_name=("修改后的测试渡槽"),
            record_data=updated_data,
            single_stake_text="K1+500",
            single_stake_value=1500.0,
        )

        updated_record = database.get_point_engineering_record(
            survey_record_id=(survey_record_id),
            form_code="form_2_3",
        )

        self.assertIsNotNone(updated_record)

        assert updated_record is not None

        self.assertEqual(
            updated_record["asset_name"],
            "修改后的测试渡槽",
        )

        self.assertEqual(
            updated_record["single_stake_text"],
            "K1+500",
        )

        self.assertAlmostEqual(
            float(updated_record["single_stake_value"]),
            1500.0,
        )

        self.assertEqual(
            updated_record["record_data"]["design_flow"],
            8.8,
        )

        self.assertEqual(
            updated_record["record_data"]["length"],
            180.0,
        )

        # 修改调查记录不能重新创建工程对象。
        self.assertEqual(
            int(updated_record["engineering_asset_id"]),
            int(result["engineering_asset_id"]),
        )

    # =========================
    # 测试6：
    # 不存在的记录应返回明确业务错误
    # =========================

    def test_update_missing_point_record_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "没有找到该调查记录",
        ):
            database.update_point_engineering_survey(
                survey_record_id=999999,
                form_code="form_2_3",
                asset_name="不存在的渡槽",
                record_data={
                    "asset_name": ("不存在的渡槽"),
                },
                single_stake_text="K9+999",
                single_stake_value=9999.0,
            )

    # =========================
    # 测试7：
    # 渡槽复用公共工程调查删除逻辑
    # =========================

    def test_delete_aqueduct_record_cleans_orphan_asset(
        self,
    ):
        result = self.create_aqueduct_draft()

        survey_record_id = int(result["survey_record_id"])

        engineering_asset_id = int(result["engineering_asset_id"])

        # 先保存一项临时评价，
        # 用于验证删除 SurveyRecord 后
        # inspection_results 外键级联正常。
        database.update_point_engineering_survey(
            survey_record_id=(survey_record_id),
            form_code="form_2_3",
            asset_name="测试渡槽",
            record_data={
                "asset_name": "测试渡槽",
                "stake": "K1+250",
                "stake_value": 1250.0,
                "design_flow": 4.5,
                "length": 120.0,
            },
            single_stake_text="K1+250",
            single_stake_value=1250.0,
            inspection_results=[
                {
                    "item_code": "TEST_01",
                    "category": "自动测试",
                    "item_name": "自动测试项目",
                    "grade": "A",
                    "description": None,
                    "remark": None,
                }
            ],
        )

        delete_result = database.delete_engineering_survey_record(
            survey_record_id=(survey_record_id),
            form_code="form_2_3",
        )

        self.assertEqual(
            delete_result["form_code"],
            "form_2_3",
        )

        self.assertEqual(
            delete_result["engineering_asset_id"],
            engineering_asset_id,
        )

        self.assertTrue(delete_result["asset_deleted"])

        self.assertEqual(
            delete_result["remaining_survey_count"],
            0,
        )

        # -------------------------
        # SurveyRecord 已删除
        # EngineeringAsset 已清理
        # InspectionResult 已级联删除
        # -------------------------

        with database.get_connection() as connection:
            record_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM survey_records
                WHERE id = ?
                """,
                (survey_record_id,),
            ).fetchone()["count"]

            asset_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM engineering_assets
                WHERE id = ?
                """,
                (engineering_asset_id,),
            ).fetchone()["count"]

            inspection_count = connection.execute(
                """
                    SELECT COUNT(*) AS count
                    FROM inspection_results
                    WHERE survey_record_id = ?
                    """,
                (survey_record_id,),
            ).fetchone()["count"]

        self.assertEqual(
            record_count,
            0,
        )

        self.assertEqual(
            asset_count,
            0,
        )

        self.assertEqual(
            inspection_count,
            0,
        )

    # =========================
    # 测试8：
    # 公共删除函数必须校验调查表归属
    # =========================

    def test_delete_point_record_rejects_wrong_form(
        self,
    ):
        result = self.create_aqueduct_draft()

        survey_record_id = int(result["survey_record_id"])

        with self.assertRaisesRegex(
            ValueError,
            "不属于当前调查表",
        ):
            database.delete_engineering_survey_record(
                survey_record_id=(survey_record_id),
                form_code="form_2_2",
            )

        # 删除失败后原记录必须仍存在。
        record = database.get_point_engineering_record(
            survey_record_id=(survey_record_id),
            form_code="form_2_3",
        )

        self.assertIsNotNone(record)

    # =========================
    # 测试9：
    # 附表2.3正式评价配置
    # =========================

    def test_aqueduct_evaluation_configuration(
        self,
    ):
        self.assertEqual(
            len(AQUEDUCT_EVALUATION_ITEMS),
            12,
        )

        # -------------------------
        # 四类项目数量
        # -------------------------

        category_counts = {}

        for item in AQUEDUCT_EVALUATION_ITEMS:
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
                "水力条件": 3,
                "结构变形": 3,
                "结构破损": 4,
                "地基基础": 2,
            },
        )

        # -------------------------
        # item_code 在本表内必须唯一
        # -------------------------

        item_codes = [item["item_code"] for item in AQUEDUCT_EVALUATION_ITEMS]

        self.assertEqual(
            len(item_codes),
            len(set(item_codes)),
        )

        # -------------------------
        # 每一项必须完整配置 A/B/C/D
        # -------------------------

        for item in AQUEDUCT_EVALUATION_ITEMS:
            self.assertEqual(
                set(item["standards"].keys()),
                {
                    "A",
                    "B",
                    "C",
                    "D",
                },
            )

    # =========================
    # 测试10：
    # 锁定原表关键评价文字
    # =========================

    def test_aqueduct_evaluation_source_text(
        self,
    ):
        items = {item["item_code"]: item for item in AQUEDUCT_EVALUATION_ITEMS}

        # 过水流量
        self.assertEqual(
            items["hydraulic_flow_capacity"]["standards"]["C"],
            ("过流能力为设计值的" "75%～90%。"),
        )

        # 槽身变形
        self.assertEqual(
            items["deformation_trough_body"]["standards"]["C"],
            ("槽身及其支承结构" "变位为20mm~50mm。"),
        )

        # 支架或支墩破损
        self.assertEqual(
            items["damage_support"]["standards"]["B"],
            "剥蚀、裂缝。",
        )

        # 原表中混凝土碳化深度
        # A、B 两级文字确实相同，
        # 程序不得自行“修正”。
        carbonation = items["damage_carbonation_depth"]["standards"]

        self.assertEqual(
            carbonation["A"],
            carbonation["B"],
        )

        self.assertEqual(
            carbonation["C"],
            ("混凝土碳化深度" "达到钢筋保护层厚度。"),
        )

        # 地基基础
        self.assertEqual(
            items["foundation_ground"]["standards"]["C"],
            "地基胀沉量为20mm～50mm。",
        )

        self.assertEqual(
            items["foundation_base"]["standards"]["D"],
            "基础倾斜、位移。",
        )

    # =========================
    # 测试11：
    # 完整渡槽草稿可以正式完成
    # =========================

    def test_complete_aqueduct_record(
        self,
    ):
        record_data = self.make_complete_record_data()

        result = database.create_engineering_survey(
            project_id=self.project_id,
            survey_batch_id=(self.batch_id),
            form_version_id=(self.form_version["id"]),
            asset_name="测试渡槽",
            asset_type="aqueduct",
            organization_unit_id=(self.office_id),
            canal_unit_id=(self.canal_id),
            business_code=("TEST-AQ-COMPLETE"),
            record_data=record_data,
            single_stake_text="K1+250",
            single_stake_value=1250.0,
            inspection_results=(self.make_complete_inspection_results()),
            survey_date="2026-09-14",
            overall_grade="B",
            survey_comment=("自动测试调查意见。"),
        )

        survey_record_id = int(result["survey_record_id"])

        complete_result = database.complete_aqueduct_record(survey_record_id)

        self.assertEqual(
            complete_result["survey_record_id"],
            survey_record_id,
        )

        self.assertEqual(
            complete_result["inspection_count"],
            12,
        )

        record = database.get_point_engineering_record(
            survey_record_id=(survey_record_id),
            form_code="form_2_3",
        )

        self.assertIsNotNone(record)

        assert record is not None

        self.assertEqual(
            record["record_status"],
            "completed",
        )

    # =========================
    # 测试12：
    # 必须完成全部12项评价
    # =========================

    def test_aqueduct_completion_requires_all_12_items(
        self,
    ):
        inspections = (self.make_complete_inspection_results())[:-1]

        result = database.create_engineering_survey(
            project_id=self.project_id,
            survey_batch_id=(self.batch_id),
            form_version_id=(self.form_version["id"]),
            asset_name=("评价不完整渡槽"),
            asset_type="aqueduct",
            organization_unit_id=(self.office_id),
            canal_unit_id=(self.canal_id),
            business_code=("TEST-AQ-INCOMPLETE"),
            record_data=(
                self.make_complete_record_data(
                    asset_name=("评价不完整渡槽"),
                    stake="K2+000",
                    stake_value=2000.0,
                )
            ),
            single_stake_text="K2+000",
            single_stake_value=2000.0,
            inspection_results=(inspections),
            survey_date="2026-09-14",
            overall_grade="B",
            survey_comment=("自动测试调查意见。"),
        )

        survey_record_id = int(result["survey_record_id"])

        with self.assertRaisesRegex(
            ValueError,
            "全部12项",
        ):
            database.complete_aqueduct_record(survey_record_id)

        record = database.get_point_engineering_record(
            survey_record_id=(survey_record_id),
            form_code="form_2_3",
        )

        self.assertIsNotNone(record)

        assert record is not None

        self.assertEqual(
            record["record_status"],
            "draft",
        )

    # =========================
    # 测试13：
    # 正式基本信息缺失不能完成
    # =========================

    def test_aqueduct_completion_requires_basic_fields(
        self,
    ):
        record_data = self.make_complete_record_data(
            stake="K3+000",
            stake_value=3000.0,
        )

        # 正式表“长度”为必填。
        record_data["length"] = None

        result = database.create_engineering_survey(
            project_id=self.project_id,
            survey_batch_id=(self.batch_id),
            form_version_id=(self.form_version["id"]),
            asset_name="缺少长度渡槽",
            asset_type="aqueduct",
            organization_unit_id=(self.office_id),
            canal_unit_id=(self.canal_id),
            business_code=("TEST-AQ-MISSING"),
            record_data=record_data,
            single_stake_text="K3+000",
            single_stake_value=3000.0,
            inspection_results=(self.make_complete_inspection_results()),
            survey_date="2026-09-14",
            overall_grade="B",
            survey_comment=("自动测试调查意见。"),
        )

        survey_record_id = int(result["survey_record_id"])

        with self.assertRaisesRegex(
            ValueError,
            "长度",
        ):
            database.complete_aqueduct_record(survey_record_id)

        record = database.get_point_engineering_record(
            survey_record_id=(survey_record_id),
            form_code="form_2_3",
        )

        self.assertIsNotNone(record)

        assert record is not None

        self.assertEqual(
            record["record_status"],
            "draft",
        )

    # =========================
    # 测试14：
    # 已完成记录允许修改，
    # 且修改后状态保持 completed
    # =========================

    def test_update_completed_aqueduct_keeps_completed_status(
        self,
    ):
        record_data = self.make_complete_record_data(
            stake="K8+000",
            stake_value=8000.0,
        )

        result = database.create_engineering_survey(
            project_id=self.project_id,
            survey_batch_id=(self.batch_id),
            form_version_id=(self.form_version["id"]),
            asset_name="已完成渡槽",
            asset_type="aqueduct",
            organization_unit_id=(self.office_id),
            canal_unit_id=(self.canal_id),
            business_code=("TEST-AQ-COMP-EDIT"),
            record_data=record_data,
            single_stake_text="K8+000",
            single_stake_value=8000.0,
            inspection_results=(self.make_complete_inspection_results()),
            survey_date="2026-09-14",
            overall_grade="B",
            survey_comment=("完成记录修改测试。"),
        )

        survey_record_id = int(result["survey_record_id"])

        database.complete_aqueduct_record(survey_record_id)

        updated_data = dict(record_data)

        updated_data["length"] = 188.0

        database.update_point_engineering_survey(
            survey_record_id=(survey_record_id),
            form_code="form_2_3",
            asset_name="已完成渡槽",
            record_data=updated_data,
            single_stake_text="K8+000",
            single_stake_value=8000.0,
            inspection_results=(self.make_complete_inspection_results()),
            survey_date="2026-09-14",
            overall_grade="A",
            survey_comment=("修改后的调查意见。"),
        )

        record = database.get_point_engineering_record(
            survey_record_id=(survey_record_id),
            form_code="form_2_3",
        )

        self.assertIsNotNone(record)

        assert record is not None

        self.assertEqual(
            record["record_status"],
            "completed",
        )

        self.assertEqual(
            record["record_data"]["length"],
            188.0,
        )

        self.assertEqual(
            record["overall_grade"],
            "A",
        )

        self.assertEqual(
            record["survey_comment"],
            "修改后的调查意见。",
        )

    # =========================================================
    # 附表2.3正式原表导出
    # =========================================================

    def test_export_aqueduct_original_form(
        self,
    ):
        record_data = self.make_complete_record_data()

        # 专门补一个加固年月，
        # 同时使用较长支撑结构名称，
        # 验证正式模板坐标。
        record_data["renovation_date"] = "2021-09"

        record_data["lower_support_structure_form"] = "排架式钢筋混凝土支撑结构"

        inspection_results = self.make_complete_inspection_results()

        # 使用循环等级，
        # 避免只验证“12个B写进去了”，
        # 同时锁定E10:E21的顺序。
        grades = (
            "A",
            "B",
            "C",
            "D",
        )

        for index, result in enumerate(inspection_results):
            result["grade"] = grades[index % len(grades)]

        create_result = database.create_engineering_survey(
            project_id=(self.project_id),
            survey_batch_id=(self.batch_id),
            form_version_id=(self.form_version["id"]),
            asset_name=("原表导出测试渡槽"),
            asset_type="aqueduct",
            organization_unit_id=(self.office_id),
            canal_unit_id=(self.canal_id),
            business_code=("TEST-AQ-EXPORT"),
            record_data=(record_data),
            single_stake_text=("K1+250"),
            single_stake_value=(1250.0),
            inspection_results=(inspection_results),
            survey_date=("2026-09-14"),
            overall_grade="C",
            survey_comment=("附表2.3原表导出测试意见。"),
        )

        survey_record_id = int(create_result["survey_record_id"])

        output_path = Path(self.temp_directory.name) / "form_2_3_export.xlsx"

        export_result = export_aqueduct_original_form(
            survey_record_id=(survey_record_id),
            file_path=(output_path),
        )

        self.assertTrue(output_path.exists())

        self.assertEqual(
            export_result["survey_record_id"],
            survey_record_id,
        )

        self.assertEqual(
            export_result["business_code"],
            "TEST-AQ-EXPORT",
        )

        workbook = load_workbook(output_path)

        self.assertIn(
            "附表2.3",
            workbook.sheetnames,
        )

        worksheet = workbook["附表2.3"]

        # -------------------------
        # 顶部归属
        # -------------------------

        self.assertEqual(
            worksheet["A3"].value,
            "测试基层",
        )

        self.assertEqual(
            worksheet["C3"].value,
            "测试水管",
        )

        self.assertEqual(
            worksheet["E3"].value,
            "测试",
        )

        self.assertEqual(
            worksheet["G3"].value,
            None,
        )

        self.assertEqual(
            worksheet["J3"].value,
            "TEST-AQ-EXPORT",
        )

        # -------------------------
        # 基本信息
        # -------------------------

        self.assertEqual(
            worksheet["B5"].value,
            "原表导出测试渡槽",
        )

        self.assertEqual(
            worksheet["H5"].value,
            "K1+250",
        )

        self.assertEqual(
            worksheet["J5"].value,
            4.5,
        )

        self.assertEqual(
            worksheet["B6"].value,
            "3级",
        )

        self.assertEqual(
            worksheet["D6"].value,
            "2010-06",
        )

        self.assertEqual(
            worksheet["F6"].value,
            "2021-09",
        )

        self.assertEqual(
            worksheet["H6"].value,
            120.0,
        )

        self.assertEqual(
            worksheet["J6"].value,
            5.5,
        )

        self.assertEqual(
            worksheet["B7"].value,
            "梁式渡槽",
        )

        self.assertEqual(
            worksheet["D7"].value,
            "3.2×2.4",
        )

        self.assertEqual(
            worksheet["F7"].value,
            "钢筋混凝土",
        )

        self.assertEqual(
            worksheet["H7"].value,
            0.25,
        )

        self.assertEqual(
            worksheet["J7"].value,
            "橡胶止水",
        )

        self.assertEqual(
            worksheet["B8"].value,
            1685.35,
        )

        self.assertEqual(
            worksheet["D8"].value,
            6,
        )

        self.assertEqual(
            worksheet["F8"].value,
            "排架式钢筋混凝土支撑结构",
        )

        # -------------------------
        # 12项评价
        # E10:E21
        # -------------------------

        expected_grades = [
            "A",
            "B",
            "C",
            "D",
            "A",
            "B",
            "C",
            "D",
            "A",
            "B",
            "C",
            "D",
        ]

        actual_grades = [
            worksheet[f"E{row_number}"].value
            for row_number in range(
                10,
                22,
            )
        ]

        self.assertEqual(
            actual_grades,
            expected_grades,
        )

        # -------------------------
        # 调查结论
        # -------------------------

        self.assertEqual(
            worksheet["C22"].value,
            "附表2.3原表导出测试意见。",
        )

        self.assertEqual(
            worksheet["J22"].value,
            "C",
        )

        self.assertEqual(
            worksheet["J23"].value,
            "2026-09-14",
        )

        # -------------------------
        # 签字区域必须保持空白
        # -------------------------

        for cell_name in (
            "B23",
            "D23",
            "F23",
            "H23",
        ):
            self.assertIsNone(worksheet[cell_name].value)

        # -------------------------
        # 正式注释必须由模板保留，
        # 导出过程不能改写。
        # -------------------------

        self.assertEqual(
            str(worksheet["A25"].value or "").strip(),
            ("注：渡槽其它部位指" "进、出口渐变段、护栏等。"),
        )

        self.assertEqual(
            worksheet.print_area,
            "'附表2.3'!$A$1:$J$26",
        )

        workbook.close()


if __name__ == "__main__":
    unittest.main()
