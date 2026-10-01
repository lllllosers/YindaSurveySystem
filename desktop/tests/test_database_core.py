import gc
import time
import sys
import sqlite3
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

from forms.engineering.registry import (
    get_engineering_form_definitions,
)

from services.business_code import (
    get_engineering_type_code,
)


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

    def test_registered_engineering_forms_are_bootstrapped(
        self,
    ):
        """
        已迁移到 EngineeringFormRegistry 的工程表，
        数据库初始化元数据必须来自并匹配正式 definition。
        """

        definitions = get_engineering_form_definitions()

        self.assertTrue(definitions)

        with database.get_connection() as connection:
            for definition in definitions:
                with self.subTest(
                    form_code=definition.form_code,
                ):
                    form = connection.execute(
                        """
                        SELECT
                            form_code,
                            form_number,
                            form_name,
                            series,
                            record_type,
                            asset_type,
                            sort_order
                        FROM form_definitions
                        WHERE form_code = ?
                        """,
                        (definition.form_code,),
                    ).fetchone()

                    self.assertIsNotNone(form)

                    assert form is not None

                    self.assertEqual(
                        form["form_code"],
                        definition.form_code,
                    )

                    self.assertEqual(
                        form["form_number"],
                        definition.form_number,
                    )

                    self.assertEqual(
                        form["form_name"],
                        definition.form_name,
                    )

                    self.assertEqual(
                        form["series"],
                        "series_2",
                    )

                    self.assertEqual(
                        form["record_type"],
                        "engineering",
                    )

                    self.assertEqual(
                        form["asset_type"],
                        definition.asset_type,
                    )

                    form_number_parts = definition.form_number.split(
                        ".",
                        1,
                    )

                    expected_sort_order = 200 + int(form_number_parts[1])

                    self.assertEqual(
                        int(form["sort_order"]),
                        expected_sort_order,
                    )

                    form_version = database.get_current_form_version(
                        definition.form_code
                    )

                    self.assertIsNotNone(form_version)

    def test_form_2_4_metadata_and_business_type_code(
        self,
    ):
        form_version = database.get_current_form_version("form_2_4")

        self.assertIsNotNone(form_version)

        self.assertEqual(
            get_engineering_type_code("form_2_4"),
            "04",
        )

        with database.get_connection() as connection:
            form = connection.execute(
                """
                SELECT
                    form_code,
                    form_number,
                    form_name,
                    series,
                    record_type,
                    asset_type,
                    sort_order
                FROM form_definitions
                WHERE form_code = ?
                """,
                ("form_2_4",),
            ).fetchone()

        self.assertIsNotNone(form)

        assert form is not None

        self.assertEqual(
            form["form_number"],
            "2.4",
        )

        self.assertEqual(
            form["form_name"],
            "倒虹吸工程状况调查表",
        )

        self.assertEqual(
            form["series"],
            "series_2",
        )

        self.assertEqual(
            form["record_type"],
            "engineering",
        )

        self.assertEqual(
            form["asset_type"],
            "inverted_siphon",
        )

        self.assertEqual(
            int(form["sort_order"]),
            204,
        )

    def test_survey_record_provenance_schema_is_core(
        self,
    ):
        """
        SurveyRecord 来源字段必须由 database.init_database()
        直接保证，不能依赖任务服务二次补列。
        """

        with database.get_connection() as connection:
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(survey_records)"
                ).fetchall()
            }
            indexes = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA index_list(survey_records)"
                ).fetchall()
            }

        self.assertIn(
            "source_task_uid",
            columns,
        )
        self.assertIn(
            "source_management_scope_uid",
            columns,
        )
        self.assertIn(
            "idx_survey_records_source_task_uid",
            indexes,
        )
        self.assertIn(
            "idx_survey_records_source_scope_uid",
            indexes,
        )

        database.init_database()

        with database.get_connection() as connection:
            columns_after = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(survey_records)"
                ).fetchall()
            }

        self.assertIn(
            "source_task_uid",
            columns_after,
        )
        self.assertIn(
            "source_management_scope_uid",
            columns_after,
        )

    def test_canal_unit_schema_is_physical_only(
        self,
    ):
        with database.get_connection() as connection:
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(canal_units)"
                ).fetchall()
            }

            foreign_keys = [
                dict(row)
                for row in connection.execute(
                    "PRAGMA foreign_key_list(canal_units)"
                ).fetchall()
            ]

        self.assertNotIn(
            "organization_unit_id",
            columns,
        )

        self.assertFalse(
            any(
                row["from"]
                == "organization_unit_id"
                for row in foreign_keys
            )
        )

        self.assertTrue(
            any(
                row["from"] == "parent_id"
                and row["table"]
                == "canal_units"
                for row in foreign_keys
            )
        )

    def test_legacy_canal_owner_schema_is_safely_migrated(
        self,
    ):
        if self.temp_db_path.exists():
            self.temp_db_path.unlink()

        raw = sqlite3.connect(
            self.temp_db_path
        )

        try:
            raw.execute(
                "PRAGMA foreign_keys = ON"
            )

            raw.executescript(
                """
                CREATE TABLE organization_units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER,
                    name TEXT NOT NULL,
                    unit_type TEXT NOT NULL,
                    business_code TEXT,
                    status TEXT NOT NULL
                        DEFAULT 'active',
                    description TEXT,
                    created_at TEXT NOT NULL
                        DEFAULT (
                            datetime(
                                'now',
                                'localtime'
                            )
                        ),
                    updated_at TEXT NOT NULL
                        DEFAULT (
                            datetime(
                                'now',
                                'localtime'
                            )
                        ),
                    FOREIGN KEY (parent_id)
                        REFERENCES organization_units(id)
                );

                CREATE TABLE canal_units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER,
                    name TEXT NOT NULL,
                    canal_level TEXT NOT NULL,
                    organization_unit_id INTEGER,
                    status TEXT NOT NULL
                        DEFAULT 'active',
                    description TEXT,
                    created_at TEXT NOT NULL
                        DEFAULT (
                            datetime(
                                'now',
                                'localtime'
                            )
                        ),
                    updated_at TEXT NOT NULL
                        DEFAULT (
                            datetime(
                                'now',
                                'localtime'
                            )
                        ),
                    canal_unit_uid TEXT,
                    master_key TEXT,
                    sort_order INTEGER
                        NOT NULL DEFAULT 0,
                    FOREIGN KEY (parent_id)
                        REFERENCES canal_units(id),
                    FOREIGN KEY (
                        organization_unit_id
                    )
                        REFERENCES organization_units(id)
                );

                CREATE TABLE canal_management_scopes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canal_unit_id INTEGER NOT NULL,
                    organization_unit_id INTEGER NOT NULL,
                    FOREIGN KEY (canal_unit_id)
                        REFERENCES canal_units(id),
                    FOREIGN KEY (
                        organization_unit_id
                    )
                        REFERENCES organization_units(id)
                );

                CREATE TABLE legacy_canal_ref (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canal_unit_id INTEGER NOT NULL,
                    FOREIGN KEY (canal_unit_id)
                        REFERENCES canal_units(id)
                );

                CREATE TABLE survey_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT
                );

                CREATE TRIGGER
                    trg_survey_records_task_scope_insert
                BEFORE INSERT ON survey_records
                FOR EACH ROW
                BEGIN
                    SELECT CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM survey_task_workspace_canals
                        )
                        THEN RAISE(
                            ABORT,
                            'stale task workspace trigger'
                        )
                    END;
                END;

                INSERT INTO organization_units (
                    id,
                    parent_id,
                    name,
                    unit_type,
                    business_code
                )
                VALUES (
                    1,
                    NULL,
                    '测试处',
                    'department',
                    '1'
                );

                INSERT INTO organization_units (
                    id,
                    parent_id,
                    name,
                    unit_type,
                    business_code
                )
                VALUES (
                    2,
                    1,
                    '测试所',
                    'water_office',
                    '01'
                );

                INSERT INTO canal_units (
                    id,
                    parent_id,
                    name,
                    canal_level,
                    organization_unit_id,
                    description,
                    canal_unit_uid,
                    master_key,
                    sort_order
                )
                VALUES (
                    10,
                    NULL,
                    '历史测试干渠',
                    '01',
                    2,
                    '迁移保留备注',
                    'legacy-canal-uid',
                    'CANAL-LEGACY-TEST',
                    123
                );

                INSERT INTO canal_management_scopes (
                    canal_unit_id,
                    organization_unit_id
                )
                VALUES (
                    10,
                    2
                );

                INSERT INTO legacy_canal_ref (
                    canal_unit_id
                )
                VALUES (
                    10
                );
                """
            )

            raw.commit()

        finally:
            raw.close()

        database.init_database()

        with database.get_connection() as connection:
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(canal_units)"
                ).fetchall()
            }

            canal = connection.execute(
                """
                SELECT
                    id,
                    name,
                    description,
                    canal_unit_uid,
                    master_key,
                    sort_order
                FROM canal_units
                WHERE id = 10
                """
            ).fetchone()

            reference = connection.execute(
                """
                SELECT canal_unit_id
                FROM legacy_canal_ref
                WHERE id = 1
                """
            ).fetchone()

            foreign_key_violations = (
                connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()
            )

            indexes = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA index_list(canal_units)"
                ).fetchall()
            }

            stale_trigger = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'trigger'
                  AND name =
                    'trg_survey_records_task_scope_insert'
                """
            ).fetchone()

        self.assertIsNone(
            stale_trigger
        )

        self.assertNotIn(
            "organization_unit_id",
            columns,
        )

        self.assertIsNotNone(
            canal
        )
        self.assertEqual(
            int(canal["id"]),
            10,
        )
        self.assertEqual(
            canal["name"],
            "历史测试干渠",
        )
        self.assertEqual(
            canal["description"],
            "迁移保留备注",
        )
        self.assertEqual(
            canal["canal_unit_uid"],
            "legacy-canal-uid",
        )
        self.assertEqual(
            canal["master_key"],
            "CANAL-LEGACY-TEST",
        )
        self.assertEqual(
            int(canal["sort_order"]),
            123,
        )

        self.assertIsNotNone(
            reference
        )
        self.assertEqual(
            int(
                reference[
                    "canal_unit_id"
                ]
            ),
            10,
        )

        self.assertEqual(
            foreign_key_violations,
            [],
        )

        self.assertIn(
            "uq_canal_units_canal_unit_uid",
            indexes,
        )
        self.assertIn(
            "uq_canal_units_master_key",
            indexes,
        )
        self.assertIn(
            "idx_canal_units_sort_order",
            indexes,
        )

        new_id = database.create_canal_unit(
            name="迁移后新增渠道",
            canal_level="01",
        )

        self.assertGreater(
            int(new_id),
            10,
        )

    def test_legacy_canal_owner_schema_refuses_unmapped_assignment(
        self,
    ):
        if self.temp_db_path.exists():
            self.temp_db_path.unlink()

        raw = sqlite3.connect(
            self.temp_db_path
        )

        try:
            raw.execute(
                "PRAGMA foreign_keys = ON"
            )

            raw.executescript(
                """
                CREATE TABLE organization_units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER,
                    name TEXT NOT NULL,
                    unit_type TEXT NOT NULL,
                    business_code TEXT,
                    status TEXT NOT NULL
                        DEFAULT 'active',
                    description TEXT,
                    created_at TEXT NOT NULL
                        DEFAULT (
                            datetime(
                                'now',
                                'localtime'
                            )
                        ),
                    updated_at TEXT NOT NULL
                        DEFAULT (
                            datetime(
                                'now',
                                'localtime'
                            )
                        ),
                    FOREIGN KEY (parent_id)
                        REFERENCES organization_units(id)
                );

                CREATE TABLE canal_units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER,
                    name TEXT NOT NULL,
                    canal_level TEXT NOT NULL,
                    organization_unit_id INTEGER,
                    status TEXT NOT NULL
                        DEFAULT 'active',
                    description TEXT,
                    created_at TEXT NOT NULL
                        DEFAULT (
                            datetime(
                                'now',
                                'localtime'
                            )
                        ),
                    updated_at TEXT NOT NULL
                        DEFAULT (
                            datetime(
                                'now',
                                'localtime'
                            )
                        ),
                    FOREIGN KEY (parent_id)
                        REFERENCES canal_units(id),
                    FOREIGN KEY (
                        organization_unit_id
                    )
                        REFERENCES organization_units(id)
                );

                INSERT INTO organization_units (
                    id,
                    parent_id,
                    name,
                    unit_type,
                    business_code
                )
                VALUES (
                    1,
                    NULL,
                    '测试处',
                    'department',
                    '1'
                );

                INSERT INTO organization_units (
                    id,
                    parent_id,
                    name,
                    unit_type,
                    business_code
                )
                VALUES (
                    2,
                    1,
                    '测试所',
                    'water_office',
                    '01'
                );

                INSERT INTO canal_units (
                    id,
                    name,
                    canal_level,
                    organization_unit_id
                )
                VALUES (
                    10,
                    '未迁移渠道',
                    '01',
                    2
                );
                """
            )

            raw.commit()

        finally:
            raw.close()

        with self.assertRaisesRegex(
            RuntimeError,
            "CanalManagementScope",
        ):
            database.init_database()

        raw = sqlite3.connect(
            self.temp_db_path
        )

        try:
            columns = {
                row[1]
                for row in raw.execute(
                    "PRAGMA table_info(canal_units)"
                ).fetchall()
            }

            row = raw.execute(
                """
                SELECT
                    id,
                    organization_unit_id
                FROM canal_units
                WHERE id = 10
                """
            ).fetchone()

        finally:
            raw.close()

        self.assertIn(
            "organization_unit_id",
            columns,
        )
        self.assertEqual(
            row,
            (
                10,
                2,
            ),
        )


if __name__ == "__main__":
    unittest.main()
