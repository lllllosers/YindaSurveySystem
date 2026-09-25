import json
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


import database

from services.engineering_original_form_export import (
    export_engineering_original_form,
)

from forms.engineering.form_2_4 import (
    FORM_2_4,
)

from tests.workflow_test_support import (
    EngineeringWorkflowTestCaseBase,
    complete_saved_engineering_record,
)

from services.inverted_siphon_evaluation import (
    INVERTED_SIPHON_EVALUATION_ITEMS,
)

from services.business_code import (
    build_business_code,
    get_engineering_type_code,
)


from openpyxl import (
    load_workbook,
)


class InvertedSiphonWorkflowTestCase(
    EngineeringWorkflowTestCaseBase,
):
    """
    附表2.4倒虹吸核心业务回归测试。

    当前阶段验证：
    - 公共点工程创建；
    - 单桩号工程身份；
    - 重复保护；
    - 公共读取和修改；
    - 公共删除；
    - 正式12项评价配置。
    """

    FORM_CODE = FORM_2_4.form_code

    TEST_DB_FILENAME = "test_inverted_siphon.db"

    PROJECT_NAME = "倒虹吸自动测试项目"
    PROJECT_SHORT_NAME = "倒虹吸测试"

    BATCH_NAME = "倒虹吸自动测试批次"
    BATCH_CODE = "IS_TEST_2026"

    # =========================================================
    # 测试数据辅助
    # =========================================================

    def create_inverted_siphon_draft(
        self,
        *,
        business_code="1-01-01-04-001",
        asset_name="测试倒虹吸",
        stake="K10+500",
        stake_value=10500.0,
    ):
        record_data = {
            "asset_name": asset_name,
            "stake": stake,
            "stake_value": stake_value,
            "start_stake": stake,
            "start_stake_value": stake_value,
            "end_stake": stake,
            "end_stake_value": stake_value,
            "design_flow": 8.5,
            "length": 260.0,
        }

        return database.create_engineering_survey(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            form_version_id=(self.form_version["id"]),
            asset_name=asset_name,
            asset_type=(self.form_version["asset_type"]),
            organization_unit_id=(self.office_id),
            canal_unit_id=self.canal_id,
            business_code=business_code,
            record_data=record_data,
            single_stake_text=stake,
            single_stake_value=stake_value,
        )

    # =========================================================
    # 1. 公共点工程创建
    # =========================================================

    def test_create_inverted_siphon_point_draft(
        self,
    ):
        result = self.create_inverted_siphon_draft()

        survey_record_id = int(result["survey_record_id"])

        engineering_asset_id = int(result["engineering_asset_id"])

        records = database.get_engineering_survey_query_records(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            form_code="form_2_4",
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
            "form_2_4",
        )

        self.assertEqual(
            record["asset_type"],
            "inverted_siphon",
        )

        self.assertEqual(
            record["asset_name"],
            "测试倒虹吸",
        )

        self.assertEqual(
            record["engineering_position"],
            "K10+500",
        )

        self.assertEqual(
            record["record_status"],
            "draft",
        )

        # 确认底层确实是单桩号工程。
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
                    ON sr.engineering_asset_id
                    = ea.id
                WHERE sr.id = ?
                """,
                (survey_record_id,),
            ).fetchone()

        self.assertIsNotNone(row)

        assert row is not None

        self.assertEqual(
            row["asset_type"],
            "inverted_siphon",
        )

        self.assertEqual(
            row["single_stake_text"],
            "K10+500",
        )

        self.assertAlmostEqual(
            float(row["single_stake_value"]),
            10500.0,
        )

        self.assertIsNone(row["start_stake_text"])

        self.assertIsNone(row["start_stake_value"])

        self.assertIsNone(row["end_stake_text"])

        self.assertIsNone(row["end_stake_value"])

        record_data = json.loads(row["record_data_json"])

        self.assertEqual(
            record_data["design_flow"],
            8.5,
        )

        self.assertEqual(
            record_data["length"],
            260.0,
        )

    # =========================================================
    # 2. 公共重复保护
    # =========================================================

    def test_duplicate_inverted_siphon_is_rejected(
        self,
    ):
        self.create_inverted_siphon_draft(
            business_code=("1-01-01-04-001"),
            asset_name="测试倒虹吸一",
            stake="K12+000",
            stake_value=12000.0,
        )

        with self.assertRaises(ValueError) as context:
            self.create_inverted_siphon_draft(
                business_code=("1-01-01-04-002"),
                asset_name="另一个倒虹吸名称",
                stake="K12+000",
                stake_value=12000.0,
            )

        self.assertIn(
            "工程调查记录",
            str(context.exception),
        )

    # =========================================================
    # 3. 公共读取和修改
    # =========================================================

    def test_get_and_update_inverted_siphon_record(
        self,
    ):
        result = self.create_inverted_siphon_draft()

        survey_record_id = int(result["survey_record_id"])

        record = database.get_point_engineering_record(
            survey_record_id=(survey_record_id),
            form_code="form_2_4",
        )

        self.assertIsNotNone(record)

        assert record is not None

        self.assertEqual(
            record["asset_type"],
            "inverted_siphon",
        )

        self.assertEqual(
            record["single_stake_text"],
            "K10+500",
        )

        updated_data = dict(record["record_data"])

        updated_data.update(
            {
                "asset_name": ("修改后的倒虹吸"),
                "stake": "K10+800",
                "stake_value": 10800.0,
                "start_stake": "K10+800",
                "start_stake_value": 10800.0,
                "end_stake": "K10+800",
                "end_stake_value": 10800.0,
                "design_flow": 9.2,
                "length": 280.0,
            }
        )

        database.update_point_engineering_survey(
            survey_record_id=(survey_record_id),
            form_code="form_2_4",
            asset_name="修改后的倒虹吸",
            record_data=updated_data,
            single_stake_text="K10+800",
            single_stake_value=10800.0,
        )

        updated_record = database.get_point_engineering_record(
            survey_record_id=(survey_record_id),
            form_code="form_2_4",
        )

        self.assertIsNotNone(updated_record)

        assert updated_record is not None

        self.assertEqual(
            updated_record["asset_name"],
            "修改后的倒虹吸",
        )

        self.assertEqual(
            updated_record["single_stake_text"],
            "K10+800",
        )

        self.assertEqual(
            updated_record["record_data"]["design_flow"],
            9.2,
        )

        self.assertEqual(
            int(updated_record["engineering_asset_id"]),
            int(result["engineering_asset_id"]),
        )

    # =========================================================
    # 4. 公共删除和孤儿工程清理
    # =========================================================

    def test_delete_inverted_siphon_record_cleans_orphan_asset(
        self,
    ):
        result = self.create_inverted_siphon_draft()

        survey_record_id = int(result["survey_record_id"])

        engineering_asset_id = int(result["engineering_asset_id"])

        database.update_point_engineering_survey(
            survey_record_id=(survey_record_id),
            form_code="form_2_4",
            asset_name="测试倒虹吸",
            record_data={
                "asset_name": "测试倒虹吸",
                "stake": "K10+500",
                "stake_value": 10500.0,
                "start_stake": "K10+500",
                "start_stake_value": 10500.0,
                "end_stake": "K10+500",
                "end_stake_value": 10500.0,
                "design_flow": 8.5,
                "length": 260.0,
            },
            single_stake_text="K10+500",
            single_stake_value=10500.0,
            inspection_results=[
                {
                    "item_code": "TEST_01",
                    "category": "自动测试",
                    "item_name": ("自动测试项目"),
                    "grade": "A",
                    "description": None,
                    "remark": None,
                }
            ],
        )

        delete_result = database.delete_engineering_survey_record(
            survey_record_id=(survey_record_id),
            form_code="form_2_4",
        )

        self.assertTrue(delete_result["asset_deleted"])

        self.assertEqual(
            delete_result["engineering_asset_id"],
            engineering_asset_id,
        )

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

    # =========================================================
    # 5. 正式评价配置结构
    # =========================================================

    def test_inverted_siphon_evaluation_configuration(
        self,
    ):
        self.assertEqual(
            len(INVERTED_SIPHON_EVALUATION_ITEMS),
            12,
        )

        category_counts = {}

        for item in INVERTED_SIPHON_EVALUATION_ITEMS:
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
                "结构变形": 2,
                "结构破损": 4,
                "涵线基础": 3,
            },
        )

        item_codes = [item["item_code"] for item in (INVERTED_SIPHON_EVALUATION_ITEMS)]

        self.assertEqual(
            len(item_codes),
            len(set(item_codes)),
        )

        for item in INVERTED_SIPHON_EVALUATION_ITEMS:
            self.assertEqual(
                set(item["standards"].keys()),
                {
                    "A",
                    "B",
                    "C",
                    "D",
                },
            )

    # =========================================================
    # 6. 锁定正式源关键文字
    # =========================================================

    def test_inverted_siphon_evaluation_source_text(
        self,
    ):
        items = {item["item_code"]: item for item in (INVERTED_SIPHON_EVALUATION_ITEMS)}

        # 正式原表这里没有“的”，
        # 不自行补写。
        self.assertEqual(
            items["hydraulic_flow_capacity"]["standards"]["C"],
            ("过流能力为设计值" "75%～90%。"),
        )

        # 正式原表D级文字确实重复，
        # 当前忠实保留。
        self.assertEqual(
            items["deformation_other_parts"]["standards"]["D"],
            ("其它部位结构变形" "不符合设计要求，" "危及工程安全。" "危及工程安全。"),
        )

        # 项目名称是“管道及其支撑”，
        # 但原表评价文字使用“洞身结构”。
        self.assertEqual(
            items["damage_pipe_support"]["standards"]["A"],
            "洞身结构完好。",
        )

        # A、B在正式原表相同。
        carbonation = items["damage_carbonation_depth"]["standards"]

        self.assertEqual(
            carbonation["A"],
            carbonation["B"],
        )

        # 正式原表类别名称。
        self.assertEqual(
            items["foundation_ground"]["category"],
            "涵线基础",
        )

        self.assertEqual(
            items["foundation_inlet_outlet"]["standards"]["D"],
            ("进、出口不均匀沉陷" "大于50mm。"),
        )

    def make_complete_record_data(
        self,
        *,
        asset_name="测试倒虹吸",
        stake="K10+500",
        stake_value=10500.0,
    ):
        return {
            "asset_name": asset_name,
            "stake": stake,
            "stake_value": stake_value,
            "start_stake": stake,
            "start_stake_value": stake_value,
            "end_stake": stake,
            "end_stake_value": stake_value,
            "design_flow": 8.5,
            "structure_grade": "3级",
            "build_date": "2010-06",
            "renovation_date": None,
            "length": 260.0,
            "increased_flow": 10.0,
            "structure_form": "埋管式",
            "section_size": "DN2400",
            "pipe_body_structure": ("钢筋混凝土"),
            "wall_thickness": 0.30,
            "waterstop_form": "橡胶止水",
            "channel_bottom_elevation": (1680.25),
        }

    def make_complete_inspection_results(
        self,
        grade="B",
    ):
        return [
            {
                "item_code": (item["item_code"]),
                "category": (item["category"]),
                "item_name": (item["item_name"]),
                "grade": grade,
                "description": None,
                "remark": None,
            }
            for item in (INVERTED_SIPHON_EVALUATION_ITEMS)
        ]

    def test_complete_inverted_siphon_through_framework(
        self,
    ):
        result = database.create_engineering_survey(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            form_version_id=(self.form_version["id"]),
            asset_name="测试倒虹吸",
            asset_type="inverted_siphon",
            organization_unit_id=(self.office_id),
            canal_unit_id=self.canal_id,
            business_code=("1-01-01-04-010"),
            record_data=(self.make_complete_record_data()),
            single_stake_text="K10+500",
            single_stake_value=10500.0,
            inspection_results=(self.make_complete_inspection_results()),
            survey_date="2026-09-14",
            overall_grade="B",
            survey_comment=("自动测试调查意见。"),
        )

        survey_record_id = int(result["survey_record_id"])

        complete_result = complete_saved_engineering_record(FORM_2_4, survey_record_id)

        self.assertEqual(
            complete_result["inspection_count"],
            12,
        )

        record = database.get_point_engineering_record(
            survey_record_id=(survey_record_id),
            form_code="form_2_4",
        )

        assert record is not None

        self.assertEqual(
            record["record_status"],
            "completed",
        )

    def test_inverted_siphon_completion_requires_all_12_items(
        self,
    ):
        inspections = (self.make_complete_inspection_results())[:-1]

        result = database.create_engineering_survey(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            form_version_id=(self.form_version["id"]),
            asset_name="评价不完整倒虹吸",
            asset_type="inverted_siphon",
            organization_unit_id=(self.office_id),
            canal_unit_id=self.canal_id,
            business_code=("1-01-01-04-011"),
            record_data=(
                self.make_complete_record_data(
                    asset_name=("评价不完整倒虹吸"),
                    stake="K11+000",
                    stake_value=11000.0,
                )
            ),
            single_stake_text="K11+000",
            single_stake_value=11000.0,
            inspection_results=inspections,
            survey_date="2026-09-14",
            overall_grade="B",
            survey_comment="自动测试。",
        )

        with self.assertRaisesRegex(
            ValueError,
            "未完成评价",
        ):
            complete_saved_engineering_record(FORM_2_4, int(result["survey_record_id"]))

    def test_inverted_siphon_completion_requires_basic_fields(
        self,
    ):
        record_data = self.make_complete_record_data(
            stake="K12+000",
            stake_value=12000.0,
        )

        record_data["section_size"] = None

        result = database.create_engineering_survey(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            form_version_id=(self.form_version["id"]),
            asset_name="缺少尺寸倒虹吸",
            asset_type="inverted_siphon",
            organization_unit_id=(self.office_id),
            canal_unit_id=self.canal_id,
            business_code=("1-01-01-04-012"),
            record_data=record_data,
            single_stake_text="K12+000",
            single_stake_value=12000.0,
            inspection_results=(self.make_complete_inspection_results()),
            survey_date="2026-09-14",
            overall_grade="B",
            survey_comment="自动测试。",
        )

        with self.assertRaisesRegex(
            ValueError,
            "尺寸",
        ):
            complete_saved_engineering_record(FORM_2_4, int(result["survey_record_id"]))

    def test_inverted_siphon_business_code_uses_type_04(
        self,
    ):
        engineering_type_code = get_engineering_type_code("form_2_4")

        self.assertEqual(
            engineering_type_code,
            "04",
        )

        business_code = build_business_code(
            department_code="1",
            water_office_code="01",
            canal_level_code="01",
            engineering_type_code=(engineering_type_code),
            sequence=1,
        )

        self.assertEqual(
            business_code,
            "1-01-01-04-001",
        )

    def test_export_inverted_siphon_original_form(
        self,
    ):
        """
        附表2.4正式原表
        应按模板坐标准确写入。
        """

        result = (
            database.create_engineering_survey(
                project_id=self.project_id,
                survey_batch_id=(
                    self.batch_id
                ),
                form_version_id=(
                    self.form_version["id"]
                ),
                asset_name=(
                    "正式导出测试倒虹吸"
                ),
                asset_type=(
                    "inverted_siphon"
                ),
                organization_unit_id=(
                    self.office_id
                ),
                canal_unit_id=(
                    self.canal_id
                ),
                business_code=(
                    "1-01-01-04-020"
                ),
                record_data=(
                    self.make_complete_record_data(
                        asset_name=(
                            "正式导出测试倒虹吸"
                        ),
                    )
                ),
                single_stake_text=(
                    "K10+500"
                ),
                single_stake_value=(
                    10500.0
                ),
                inspection_results=(
                    self.make_complete_inspection_results(
                        grade="B"
                    )
                ),
                survey_date=(
                    "2026-09-14"
                ),
                overall_grade="C",
                survey_comment=(
                    "倒虹吸正式导出测试。"
                ),
            )
        )

        survey_record_id = int(
            result["survey_record_id"]
        )

        output_path = (
            Path(
                self.temp_directory.name
            )
            / "form_2_4_export.xlsx"
        )

        export_engineering_original_form(
            FORM_2_4,
            survey_record_id=(
                survey_record_id
            ),
            file_path=output_path,
        )

        self.assertTrue(
            output_path.exists()
        )

        workbook = load_workbook(
            output_path,
            data_only=False,
        )

        worksheet = workbook[
            "附表2.4"
        ]

        self.assertEqual(
            worksheet["B5"].value,
            "正式导出测试倒虹吸",
        )

        self.assertEqual(
            worksheet["H5"].value,
            "K10+500～K10+500",
        )

        self.assertEqual(
            worksheet["J5"].value,
            8.5,
        )

        self.assertEqual(
            worksheet["D7"].value,
            "DN2400",
        )

        self.assertEqual(
            worksheet["F7"].value,
            "钢筋混凝土",
        )

        self.assertEqual(
            worksheet["B8"].value,
            1680.25,
        )

        # 12项评价均为B。
        for row_number in range(
            10,
            22,
        ):
            self.assertEqual(
                worksheet[
                    f"E{row_number}"
                ].value,
                "B",
            )

        self.assertEqual(
            worksheet["C22"].value,
            "倒虹吸正式导出测试。",
        )

        self.assertEqual(
            worksheet["J22"].value,
            "C",
        )

        self.assertEqual(
            worksheet["J23"].value,
            "2026-09-14",
        )

        # 签字格保持空白。
        self.assertIsNone(
            worksheet["B23"].value
        )

        workbook.close()

if __name__ == "__main__":
    unittest.main()
