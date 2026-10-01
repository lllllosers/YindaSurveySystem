import gc
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import database
from services.application_bootstrap import initialize_application_database
from services.canal_management_scope import (
    RANGE_MODE_SEGMENT_KNOWN,
    RANGE_MODE_SEGMENT_UNKNOWN,
    create_canal_management_scope,
    ensure_canal_management_scope_schema,
    find_management_scope_for_stake,
    get_canal_management_scope,
    get_management_scopes_for_canal,
    get_management_scopes_for_organization,
    organization_manages_canal,
)
from services.master_identity import deterministic_master_uid


class CanalManagementScopeTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_directory.name)
        self.original_data_dir = database.DATA_DIR
        self.original_db_path = database.DB_PATH
        database.DATA_DIR = self.temp_root / "local_data"
        database.DB_PATH = database.DATA_DIR / "scope.db"
        initialize_application_database()

    def tearDown(self):
        gc.collect()
        database.DATA_DIR = self.original_data_dir
        database.DB_PATH = self.original_db_path
        self.temp_directory.cleanup()

    def _office_id(self, master_key):
        with database.get_connection() as connection:
            row = connection.execute(
                "SELECT id FROM organization_units WHERE master_key = ?",
                (master_key,),
            ).fetchone()
        self.assertIsNotNone(row)
        return int(row["id"])

    def _manual_canal(self, name):
        with database.get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO canal_units (
                    name,
                    canal_level,
                    status,
                    sort_order
                )
                VALUES (?, '01', 'active', 99000)
                """,
                (name,),
            )
            return int(cursor.lastrowid)

    def test_official_scope_has_deterministic_uid(self):
        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT cms.master_key, cms.management_scope_uid, cms.range_mode
                FROM canal_management_scopes AS cms
                JOIN canal_units AS canal
                  ON canal.id = cms.canal_unit_id
                JOIN organization_units AS office
                  ON office.id = cms.organization_unit_id
                WHERE canal.master_key = 'CANAL-S001'
                  AND office.master_key = 'ORG-D01-O03'
                """
            ).fetchone()

        self.assertIsNotNone(row)
        key = "CMS-CANAL-S001-ORG-D01-O03"
        self.assertEqual(row["master_key"], key)
        self.assertEqual(
            row["management_scope_uid"],
            deterministic_master_uid("canal_management_scope", key),
        )
        self.assertEqual(row["range_mode"], "whole")

    def test_trunk_canal_is_not_guessed(self):
        with database.get_connection() as connection:
            trunk = connection.execute(
                "SELECT id FROM canal_units WHERE master_key = 'CANAL-G01'"
            ).fetchone()
        self.assertIsNotNone(trunk)
        self.assertEqual(
            get_management_scopes_for_canal(int(trunk["id"])),
            [],
        )

    def test_scope_schema_is_idempotent(
        self,
    ):
        first = (
            ensure_canal_management_scope_schema()
        )
        second = (
            ensure_canal_management_scope_schema()
        )

        self.assertEqual(
            first[
                "total_scope_count"
            ],
            second[
                "total_scope_count"
            ],
        )

    def test_segment_unknown_does_not_guess_by_stake(self):
        canal_id = self._manual_canal("测试未知边界干渠")
        office_id = self._office_id("ORG-D01-O01")
        create_canal_management_scope(
            canal_unit_id=canal_id,
            organization_unit_id=office_id,
            range_mode=RANGE_MODE_SEGMENT_UNKNOWN,
        )

        result = find_management_scope_for_stake(canal_id, 12.345)
        self.assertEqual(result["status"], "unresolved")
        self.assertIsNone(result["scope"])
        self.assertTrue(organization_manages_canal(office_id, canal_id))
        self.assertTrue(
            any(
                item["canal_unit_id"] == canal_id
                for item in get_management_scopes_for_organization(office_id)
            )
        )

    def test_known_segments_resolve_and_overlap_is_visible(self):
        canal_id = self._manual_canal("测试已知边界干渠")
        first_office = self._office_id("ORG-D01-O01")
        second_office = self._office_id("ORG-D01-O02")

        create_canal_management_scope(
            canal_unit_id=canal_id,
            organization_unit_id=first_office,
            range_mode=RANGE_MODE_SEGMENT_KNOWN,
            start_stake_text="K0+000",
            start_stake_value=0.0,
            end_stake_text="K10+000",
            end_stake_value=10.0,
        )
        create_canal_management_scope(
            canal_unit_id=canal_id,
            organization_unit_id=second_office,
            range_mode=RANGE_MODE_SEGMENT_KNOWN,
            start_stake_text="K8+000",
            start_stake_value=8.0,
            end_stake_text="K20+000",
            end_stake_value=20.0,
        )

        resolved = find_management_scope_for_stake(canal_id, 5.0)
        self.assertEqual(resolved["status"], "matched")
        self.assertEqual(
            resolved["scope"]["organization_unit_id"],
            first_office,
        )

        overlap = find_management_scope_for_stake(canal_id, 9.0)
        self.assertEqual(overlap["status"], "ambiguous")
        self.assertEqual(len(overlap["candidate_scopes"]), 2)

    def test_invalid_range_is_rejected(self):
        canal_id = self._manual_canal("测试错误范围干渠")
        office_id = self._office_id("ORG-D01-O01")
        with self.assertRaises(ValueError):
            create_canal_management_scope(
                canal_unit_id=canal_id,
                organization_unit_id=office_id,
                range_mode=RANGE_MODE_SEGMENT_KNOWN,
                start_stake_value=20.0,
                end_stake_value=10.0,
            )


    def test_scope_can_be_loaded_by_uid_including_inactive(self):
        canal_id = self._manual_canal(
            "测试稳定UID查询干渠"
        )
        office_id = self._office_id(
            "ORG-D01-O01"
        )

        created = create_canal_management_scope(
            canal_unit_id=canal_id,
            organization_unit_id=office_id,
            range_mode=RANGE_MODE_SEGMENT_UNKNOWN,
        )

        loaded = get_canal_management_scope(
            created["management_scope_uid"]
        )

        self.assertIsNotNone(loaded)
        self.assertEqual(
            loaded["id"],
            created["id"],
        )
        self.assertEqual(
            loaded["canal_unit_id"],
            canal_id,
        )
        self.assertEqual(
            loaded["organization_unit_id"],
            office_id,
        )
        self.assertEqual(
            loaded["status"],
            "active",
        )

        with database.get_connection() as connection:
            connection.execute(
                """
                UPDATE canal_management_scopes
                SET status = 'inactive'
                WHERE management_scope_uid = ?
                """,
                (
                    created["management_scope_uid"],
                ),
            )

        inactive = get_canal_management_scope(
            created["management_scope_uid"]
        )

        self.assertIsNotNone(inactive)
        self.assertEqual(
            inactive["status"],
            "inactive",
        )

        self.assertIsNone(
            get_canal_management_scope(
                "missing-management-scope-uid"
            )
        )


if __name__ == "__main__":
    unittest.main()
