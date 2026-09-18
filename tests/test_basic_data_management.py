import inspect
import gc
import sys
import tempfile
import time
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
from services.canal_management_scope import (
    RANGE_MODE_WHOLE,
    create_canal_management_scope,
    ensure_canal_management_scope_schema,
)


class BasicDataManagementTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()

        self.temp_data_dir = Path(self.temp_directory.name) / "local_data"

        self.temp_db_path = self.temp_data_dir / "test_yinda_survey.db"

        self.original_data_dir = database.DATA_DIR
        self.original_db_path = database.DB_PATH

        database.DATA_DIR = self.temp_data_dir
        database.DB_PATH = self.temp_db_path

        database.init_database()
        database.create_initial_forms()

    def tearDown(self):
        database.DATA_DIR = self.original_data_dir
        database.DB_PATH = self.original_db_path

        gc.collect()
        time.sleep(0.05)

        self.temp_directory.cleanup()

    def create_base_data(self):
        project = database.create_project(
            name="基础资料测试项目",
        )

        department_id = database.create_organization_unit(
            name="测试管理处",
            unit_type="department",
            business_code="1",
        )

        office_id = database.create_organization_unit(
            name="测试水管所",
            unit_type="water_office",
            business_code="01",
            parent_id=department_id,
        )

        canal_id = database.create_canal_unit(
            name="测试渠道",
            canal_level="01",

        )

        return (
            int(project["project_id"]),
            department_id,
            office_id,
            canal_id,
        )

    def create_asset_reference(
        self,
        project_id,
        office_id,
        canal_id,
    ):
        with database.get_connection() as connection:
            connection.execute(
                """
                INSERT INTO engineering_assets (
                    project_id,
                    asset_name,
                    asset_type,
                    organization_unit_id,
                    canal_unit_id,
                    business_code
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    "测试工程",
                    "sluice_gate",
                    office_id,
                    canal_id,
                    "1-01-01-02-001",
                ),
            )

    def test_unreferenced_organization_can_edit_toggle_and_delete(
        self,
    ):
        department_id = database.create_organization_unit(
            name="临时管理处",
            unit_type="department",
            business_code="9",
        )

        database.update_organization_unit(
            unit_id=department_id,
            name="修改后的管理处",
            business_code="8",
            description="修改成功",
        )

        row = database.get_organization_unit(department_id)

        self.assertEqual(
            row["name"],
            "修改后的管理处",
        )
        self.assertEqual(
            row["business_code"],
            "8",
        )

        database.set_organization_unit_status(
            department_id,
            "inactive",
        )

        row = database.get_organization_unit(department_id)

        self.assertEqual(
            row["status"],
            "inactive",
        )

        database.delete_organization_unit(department_id)

        self.assertIsNone(database.get_organization_unit(department_id))

    def test_referenced_organization_locks_business_code_but_allows_name_and_status(
        self,
    ):
        (
            project_id,
            department_id,
            office_id,
            canal_id,
        ) = self.create_base_data()

        self.create_asset_reference(
            project_id,
            office_id,
            canal_id,
        )

        database.update_organization_unit(
            unit_id=office_id,
            name="新水管所名称",
            business_code="01",
            parent_id=department_id,
            description="允许修改名称",
        )

        with self.assertRaises(ValueError):
            database.update_organization_unit(
                unit_id=office_id,
                name="新水管所名称",
                business_code="02",
                parent_id=department_id,
            )

        # 基层处业务代码也应因为下属水管所
        # 已产生工程数据而锁定。
        with self.assertRaises(ValueError):
            database.update_organization_unit(
                unit_id=department_id,
                name="测试管理处",
                business_code="2",
            )

        database.set_organization_unit_status(
            office_id,
            "inactive",
        )

        with self.assertRaises(ValueError):
            database.delete_organization_unit(office_id)

    def test_organization_with_children_cannot_be_deleted(
        self,
    ):
        (
            _,
            department_id,
            _,
            _,
        ) = self.create_base_data()

        with self.assertRaises(ValueError):
            database.delete_organization_unit(department_id)

    def test_referenced_canal_locks_structure_but_allows_name_and_status(
        self,
    ):
        (
            project_id,
            _,
            office_id,
            canal_id,
        ) = self.create_base_data()

        self.create_asset_reference(
            project_id,
            office_id,
            canal_id,
        )

        database.update_canal_unit(
            canal_unit_id=canal_id,
            name="修改后的渠道名称",
            canal_level="01",
            parent_id=None,

            description="名称允许修改",
        )

        row = database.get_canal_unit(canal_id)

        self.assertEqual(
            row["name"],
            "修改后的渠道名称",
        )

        with self.assertRaises(ValueError):
            database.update_canal_unit(
                canal_unit_id=canal_id,
                name="修改后的渠道名称",
                canal_level="02",
                parent_id=None,

            )

        database.set_canal_unit_status(
            canal_id,
            "inactive",
        )

        with self.assertRaises(ValueError):
            database.delete_canal_unit(canal_id)

    def test_canal_with_child_cannot_be_deleted_but_leaf_can(
        self,
    ):
        (
            _,
            _,
            office_id,
            parent_canal_id,
        ) = self.create_base_data()

        child_canal_id = database.create_canal_unit(
            name="测试子渠道",
            canal_level="03",
            parent_id=parent_canal_id,

        )

        with self.assertRaises(ValueError):
            database.delete_canal_unit(parent_canal_id)

        database.delete_canal_unit(child_canal_id)

        self.assertIsNone(database.get_canal_unit(child_canal_id))

    def test_canal_api_exposes_only_physical_structure_fields(
        self,
    ):
        self.assertNotIn(
            "organization_unit_id",
            inspect.signature(
                database.create_canal_unit
            ).parameters,
        )
        self.assertNotIn(
            "organization_unit_id",
            inspect.signature(
                database.update_canal_unit
            ).parameters,
        )
        self.assertFalse(
            hasattr(
                database,
                "get_canal_units_for_organization",
            )
        )
    def test_organization_usage_is_driven_by_management_scope(
        self,
    ):
        (
            _,
            _,
            office_id,
            canal_id,
        ) = self.create_base_data()

        before = (
            database.get_organization_unit_usage(
                office_id
            )
        )

        self.assertNotIn(
            "canal_count",
            before,
        )
        self.assertEqual(
            before[
                "management_scope_count"
            ],
            0,
        )

        ensure_canal_management_scope_schema()

        create_canal_management_scope(
            canal_unit_id=canal_id,
            organization_unit_id=office_id,
            range_mode=RANGE_MODE_WHOLE,
        )

        after = (
            database.get_organization_unit_usage(
                office_id
            )
        )

        self.assertEqual(
            after[
                "management_scope_count"
            ],
            1,
        )
        self.assertFalse(
            after[
                "can_delete"
            ]
        )

        with self.assertRaises(
            ValueError
        ):
            database.delete_organization_unit(
                office_id
            )


if __name__ == "__main__":
    unittest.main()
