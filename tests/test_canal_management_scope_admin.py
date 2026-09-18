import gc
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


import database

from services.application_bootstrap import (
    initialize_application_database,
)
from services.canal_management_scope_admin import (
    create_management_scope,
    delete_management_scope,
    get_canal_management_summary_map,
    set_management_scope_status,
    update_management_scope,
)


class CanalManagementScopeAdminTestCase(
    unittest.TestCase,
):
    def setUp(self):
        self.temp_directory = (
            tempfile.TemporaryDirectory()
        )

        self.temp_root = Path(
            self.temp_directory.name
        )

        self.original_data_dir = (
            database.DATA_DIR
        )
        self.original_db_path = (
            database.DB_PATH
        )

        database.DATA_DIR = (
            self.temp_root
            / "local_data"
        )

        database.DB_PATH = (
            database.DATA_DIR
            / "scope_admin.db"
        )

        initialize_application_database()

    def tearDown(self):
        gc.collect()

        database.DATA_DIR = (
            self.original_data_dir
        )
        database.DB_PATH = (
            self.original_db_path
        )

        self.temp_directory.cleanup()

    def _id(
        self,
        table,
        master_key,
    ):
        with database.get_connection() as connection:
            row = connection.execute(
                f"""
                SELECT id
                FROM {table}
                WHERE master_key = ?
                """,
                (
                    master_key,
                ),
            ).fetchone()

        self.assertIsNotNone(
            row
        )

        return int(
            row[
                "id"
            ]
        )

    def test_trunk_can_accept_multiple_unknown_segments(
        self,
    ):
        canal_id = self._id(
            "canal_units",
            "CANAL-G01",
        )

        first_office = self._id(
            "organization_units",
            "ORG-D01-O01",
        )

        second_office = self._id(
            "organization_units",
            "ORG-D01-O02",
        )

        first = create_management_scope(
            canal_unit_id=canal_id,
            organization_unit_id=first_office,
            range_mode="segment_unknown",
        )

        second = create_management_scope(
            canal_unit_id=canal_id,
            organization_unit_id=second_office,
            range_mode="segment_unknown",
        )

        self.assertEqual(
            first[
                "range_mode"
            ],
            "segment_unknown",
        )
        self.assertEqual(
            second[
                "range_mode"
            ],
            "segment_unknown",
        )

        summary = (
            get_canal_management_summary_map()
        )

        self.assertIn(
            "分段/边界未知",
            summary[
                canal_id
            ],
        )

    def test_whole_scope_cannot_coexist_with_active_segment(
        self,
    ):
        canal_id = self._id(
            "canal_units",
            "CANAL-G01",
        )

        first_office = self._id(
            "organization_units",
            "ORG-D01-O01",
        )

        second_office = self._id(
            "organization_units",
            "ORG-D01-O02",
        )

        create_management_scope(
            canal_unit_id=canal_id,
            organization_unit_id=first_office,
            range_mode="segment_unknown",
        )

        with self.assertRaises(
            ValueError
        ):
            create_management_scope(
                canal_unit_id=canal_id,
                organization_unit_id=second_office,
                range_mode="whole",
            )

    def test_official_scope_cannot_be_physically_deleted(
        self,
    ):
        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT management_scope_uid
                FROM canal_management_scopes
                WHERE master_key =
                    'CMS-CANAL-S001-ORG-D01-O03'
                """
            ).fetchone()

        self.assertIsNotNone(
            row
        )

        with self.assertRaises(
            ValueError
        ):
            delete_management_scope(
                row[
                    "management_scope_uid"
                ]
            )

    def test_manual_scope_can_edit_toggle_and_delete(
        self,
    ):
        canal_id = self._id(
            "canal_units",
            "CANAL-G01",
        )

        office_id = self._id(
            "organization_units",
            "ORG-D01-O01",
        )

        scope = create_management_scope(
            canal_unit_id=canal_id,
            organization_unit_id=office_id,
            range_mode="segment_unknown",
            description="初始说明",
        )

        updated = update_management_scope(
            scope[
                "management_scope_uid"
            ],
            organization_unit_id=office_id,
            range_mode="segment_known",
            start_stake_text="CH1+000",
            start_stake_value=1000.0,
            end_stake_text="CH2+000",
            end_stake_value=2000.0,
            description="补充正式边界",
        )

        self.assertEqual(
            updated[
                "range_mode"
            ],
            "segment_known",
        )

        inactive = set_management_scope_status(
            scope[
                "management_scope_uid"
            ],
            "inactive",
        )

        self.assertEqual(
            inactive[
                "status"
            ],
            "inactive",
        )

        delete_management_scope(
            scope[
                "management_scope_uid"
            ]
        )

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM canal_management_scopes
                WHERE management_scope_uid = ?
                """,
                (
                    scope[
                        "management_scope_uid"
                    ],
                ),
            ).fetchone()

        self.assertIsNone(
            row
        )

    def test_scope_references_block_canal_and_office_deletion(
        self,
    ):
        department_id = (
            database.create_organization_unit(
                name="临时处",
                unit_type="department",
                business_code="9",
            )
        )

        office_id = (
            database.create_organization_unit(
                name="临时所",
                unit_type="water_office",
                business_code="01",
                parent_id=department_id,
            )
        )

        canal_id = (
            database.create_canal_unit(
                name="临时干渠",
                canal_level="01",
            )
        )

        scope = create_management_scope(
            canal_unit_id=canal_id,
            organization_unit_id=office_id,
            range_mode="segment_unknown",
        )

        canal_usage = (
            database.get_canal_unit_usage(
                canal_id
            )
        )
        office_usage = (
            database.get_organization_unit_usage(
                office_id
            )
        )

        self.assertEqual(
            canal_usage[
                "management_scope_count"
            ],
            1,
        )
        self.assertEqual(
            office_usage[
                "management_scope_count"
            ],
            1,
        )

        with self.assertRaises(
            ValueError
        ):
            database.delete_canal_unit(
                canal_id
            )

        with self.assertRaises(
            ValueError
        ):
            database.delete_organization_unit(
                office_id
            )

        delete_management_scope(
            scope[
                "management_scope_uid"
            ]
        )

        database.delete_canal_unit(
            canal_id
        )
        database.delete_organization_unit(
            office_id
        )


if __name__ == "__main__":
    unittest.main()
