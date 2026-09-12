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


class DatabaseCoreTestCase(unittest.TestCase):
    """
    数据库核心业务回归测试。

    每个测试都会使用独立的临时 SQLite 数据库，
    不会接触正式 local_data/yinda_survey.db。
    """

    def setUp(self):
        # =========================
        # 创建临时目录
        # =========================

        self.temp_directory = tempfile.TemporaryDirectory()

        self.temp_data_dir = Path(self.temp_directory.name) / "local_data"

        self.temp_db_path = self.temp_data_dir / "test_yinda_survey.db"

        # 保存 database.py 原始路径，
        # 测试结束后恢复。
        self.original_data_dir = database.DATA_DIR

        self.original_db_path = database.DB_PATH

        # =========================
        # 将数据库模块临时指向测试库
        # =========================

        database.DATA_DIR = self.temp_data_dir

        database.DB_PATH = self.temp_db_path

        # 每个测试都从全新数据库开始。
        database.init_database()
        database.create_initial_forms()

    def tearDown(self):
        # =========================
        # 恢复正式数据库路径
        # =========================

        database.DATA_DIR = self.original_data_dir

        database.DB_PATH = self.original_db_path

        # =========================
        # 强制回收 SQLite 连接对象
        # =========================
        #
        # sqlite3.Connection 作为上下文管理器退出时，
        # 会提交/回滚事务，但不保证立即 close。
        #
        # Windows 对正在占用的 SQLite 文件不能直接删除，
        # 因此测试结束前主动触发垃圾回收，
        # 等待文件句柄释放。

        gc.collect()
        time.sleep(0.05)

        self.temp_directory.cleanup()

    # =========================
    # 辅助方法
    # =========================

    def create_basic_project_context(
        self,
    ):
        """
        创建：
        - 1个当前项目
        - 1个当前调查批次

        返回 project_id, batch_id。
        """

        project_result = database.create_project(
            name="自动测试项目",
            short_name="测试项目",
            description="自动化测试",
        )

        project_id = int(project_result["project_id"])

        batch_result = database.create_survey_batch(
            project_id=project_id,
            batch_name="自动测试批次",
            batch_code="TEST_001",
            start_date="2026-09-01",
            end_date="2026-12-31",
            description="自动化测试",
        )

        batch_id = int(batch_result["batch_id"])

        return (
            project_id,
            batch_id,
        )

    # =========================
    # 测试1：
    # 第一个项目和批次自动成为当前
    # =========================

    def test_first_project_and_batch_become_active(
        self,
    ):
        project_id, batch_id = self.create_basic_project_context()

        context = database.get_current_context()

        self.assertIsNotNone(context)

        assert context is not None

        self.assertEqual(
            int(context["project_id"]),
            project_id,
        )

        self.assertEqual(
            int(context["batch_id"]),
            batch_id,
        )

        self.assertEqual(
            context["project_name"],
            "自动测试项目",
        )

        self.assertEqual(
            context["batch_name"],
            "自动测试批次",
        )

    # =========================
    # 测试2：
    # 调查批次切换应同步切换当前项目
    # =========================

    def test_switch_batch_also_switches_project(
        self,
    ):
        # 第一个项目
        project_1 = database.create_project(
            name="项目一",
            short_name="P1",
        )

        project_1_id = int(project_1["project_id"])

        batch_1 = database.create_survey_batch(
            project_id=project_1_id,
            batch_name="项目一批次",
            batch_code="P1_2026",
        )

        # 第二个项目
        project_2 = database.create_project(
            name="项目二",
            short_name="P2",
        )

        project_2_id = int(project_2["project_id"])

        self.assertEqual(
            project_2["status"],
            "inactive",
        )

        batch_2 = database.create_survey_batch(
            project_id=project_2_id,
            batch_name="项目二批次",
            batch_code="P2_2026",
        )

        batch_2_id = int(batch_2["batch_id"])

        # 第二项目当前不是 active，
        # 所以它的新批次应先是 draft。
        self.assertEqual(
            batch_2["status"],
            "draft",
        )

        # 直接把第二项目的批次设为当前。
        database.set_active_survey_batch(batch_2_id)

        context = database.get_current_context()

        self.assertIsNotNone(context)

        assert context is not None

        self.assertEqual(
            int(context["project_id"]),
            project_2_id,
        )

        self.assertEqual(
            int(context["batch_id"]),
            batch_2_id,
        )

        self.assertEqual(
            context["project_name"],
            "项目二",
        )

        self.assertEqual(
            context["batch_name"],
            "项目二批次",
        )

        # 原项目的批次不应继续作为当前批次。
        batches_1 = database.get_survey_batches(project_1_id)

        self.assertEqual(
            len(batches_1),
            1,
        )

        # project_1 的批次虽然可以仍记录 active，
        # 但由于 project_1 已经 inactive，
        # get_current_context 不得再把它当当前上下文。
        self.assertNotEqual(
            int(context["project_id"]),
            project_1_id,
        )

    # =========================
    # 测试3：
    # readiness 随基础资料逐步变完整
    # =========================

    def test_survey_readiness_progression(
        self,
    ):
        self.create_basic_project_context()

        # 一开始没有任何基础资料。
        readiness = database.get_survey_readiness()

        self.assertFalse(readiness["ready"])

        self.assertEqual(
            readiness["department_count"],
            0,
        )

        self.assertEqual(
            readiness["office_count"],
            0,
        )

        self.assertEqual(
            readiness["canal_count"],
            0,
        )

        # -------------------------
        # 新增基层处
        # -------------------------

        database.create_organization_unit(
            name="测试基层处",
            unit_type="department",
            business_code="01",
        )

        departments = database.get_departments()

        self.assertEqual(
            len(departments),
            1,
        )

        department_id = int(departments[0]["id"])

        readiness = database.get_survey_readiness()

        self.assertFalse(readiness["ready"])

        self.assertEqual(
            readiness["department_count"],
            1,
        )

        self.assertEqual(
            readiness["office_count"],
            0,
        )

        # -------------------------
        # 新增水管所
        # -------------------------

        database.create_organization_unit(
            name="测试水管所",
            unit_type="water_office",
            business_code="01",
            parent_id=department_id,
        )

        offices = database.get_water_offices(department_id)

        self.assertEqual(
            len(offices),
            1,
        )

        office_id = int(offices[0]["id"])

        readiness = database.get_survey_readiness()

        self.assertFalse(readiness["ready"])

        self.assertEqual(
            readiness["office_count"],
            1,
        )

        self.assertEqual(
            readiness["canal_count"],
            0,
        )

        # -------------------------
        # 新增渠系
        # -------------------------

        database.create_canal_unit(
            name="测试干渠",
            canal_level="01",
            parent_id=None,
            organization_unit_id=office_id,
            description="自动测试",
        )

        readiness = database.get_survey_readiness()

        self.assertTrue(readiness["ready"])

        self.assertEqual(
            readiness["department_count"],
            1,
        )

        self.assertEqual(
            readiness["office_count"],
            1,
        )

        self.assertEqual(
            readiness["canal_count"],
            1,
        )

        self.assertEqual(
            readiness["missing"],
            [],
        )

    # =========================
    # 测试4：
    # 项目和批次重复保护
    # =========================

    def test_duplicate_project_and_batch_are_rejected(
        self,
    ):
        project_result = database.create_project(
            name="重复测试项目",
            short_name="重复测试",
        )

        project_id = int(project_result["project_id"])

        with self.assertRaises(ValueError):
            database.create_project(
                name="重复测试项目",
                short_name="另一个简称",
            )

        database.create_survey_batch(
            project_id=project_id,
            batch_name="第一批次",
            batch_code="DUPLICATE",
        )

        with self.assertRaises(ValueError):
            database.create_survey_batch(
                project_id=project_id,
                batch_name="第二批次",
                batch_code="DUPLICATE",
            )


if __name__ == "__main__":
    unittest.main()
