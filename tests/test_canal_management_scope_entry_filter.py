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
from services.canal_management_scope import (
    RANGE_MODE_SEGMENT_UNKNOWN,
    create_canal_management_scope,
    get_managed_canals_for_organization,
)


class CanalManagementScopeEntryFilterTestCase(
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
            / "entry_filter.db"
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

    def _id_by_master_key(
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

    def _managed_ids(
        self,
        organization_unit_id,
        *,
        active_only=True,
    ):
        return {
            int(
                row[
                    "id"
                ]
            )
            for row in (
                get_managed_canals_for_organization(
                    organization_unit_id,
                    active_only=active_only,
                )
            )
        }

    def test_official_scope_drives_entry_filter(
        self,
    ):
        office_id = (
            self._id_by_master_key(
                "organization_units",
                "ORG-D01-O03",
            )
        )

        canal_id = (
            self._id_by_master_key(
                "canal_units",
                "CANAL-S001",
            )
        )

        self.assertIn(
            canal_id,
            self._managed_ids(
                office_id
            ),
        )

    def test_multiple_scopes_for_same_canal_are_deduplicated(
        self,
    ):
        office_id = (
            self._id_by_master_key(
                "organization_units",
                "ORG-D01-O03",
            )
        )

        canal_id = (
            self._id_by_master_key(
                "canal_units",
                "CANAL-S001",
            )
        )

        create_canal_management_scope(
            canal_unit_id=canal_id,
            organization_unit_id=office_id,
            range_mode=(
                RANGE_MODE_SEGMENT_UNKNOWN
            ),
            sort_order=99999,
            description=(
                "仅用于验证同一渠道多范围去重"
            ),
        )

        managed = (
            get_managed_canals_for_organization(
                office_id
            )
        )

        matches = [
            row
            for row in managed
            if int(
                row[
                    "id"
                ]
            )
            == canal_id
        ]

        self.assertEqual(
            len(
                matches
            ),
            1,
        )

    def test_inactive_scope_is_hidden_for_new_entry_but_available_for_history(
        self,
    ):
        office_id = (
            self._id_by_master_key(
                "organization_units",
                "ORG-D01-O03",
            )
        )

        canal_id = (
            self._id_by_master_key(
                "canal_units",
                "CANAL-S001",
            )
        )

        with database.get_connection() as connection:
            connection.execute(
                """
                UPDATE canal_management_scopes
                SET status = 'inactive'
                WHERE
                    canal_unit_id = ?
                    AND organization_unit_id = ?
                """,
                (
                    canal_id,
                    office_id,
                ),
            )

        self.assertNotIn(
            canal_id,
            self._managed_ids(
                office_id,
                active_only=True,
            ),
        )

        self.assertIn(
            canal_id,
            self._managed_ids(
                office_id,
                active_only=False,
            ),
        )


if __name__ == "__main__":
    unittest.main()
