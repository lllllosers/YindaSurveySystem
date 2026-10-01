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
from services.engineering_numbering import (
    preview_engineering_business_code_renumber,
    renumber_engineering_business_codes,
)


class V102EngineeringNumberingTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.original_data_dir = database.DATA_DIR
        self.original_db_path = database.DB_PATH
        database.DATA_DIR = Path(self.temp_directory.name) / "local_data"
        database.DB_PATH = database.DATA_DIR / "numbering.db"
        initialize_application_database()

        project = database.create_project(name="编号排序测试", short_name="排序")
        self.project_id = int(project["project_id"])
        batch = database.create_survey_batch(
            project_id=self.project_id,
            batch_name="编号排序批次",
            batch_code="NUMBERING-102",
        )
        self.batch_id = int(batch["batch_id"])

        with database.get_connection() as connection:
            office = connection.execute(
                """
                SELECT office.id
                FROM organization_units AS office
                JOIN organization_units AS department
                  ON department.id = office.parent_id
                WHERE office.unit_type = 'water_office'
                  AND office.status = 'active'
                  AND office.business_code IS NOT NULL
                  AND department.business_code IS NOT NULL
                ORDER BY office.id
                LIMIT 1
                """
            ).fetchone()
            canals = connection.execute(
                """
                SELECT id
                FROM canal_units
                WHERE status = 'active'
                  AND canal_level IN ('01','02','03','04')
                ORDER BY id
                LIMIT 2
                """
            ).fetchall()
            forms = connection.execute(
                """
                SELECT fv.id AS form_version_id, fd.asset_type
                FROM form_definitions AS fd
                JOIN form_versions AS fv
                  ON fv.form_definition_id = fd.id
                WHERE fd.series = 'series_2'
                  AND fd.record_type = 'engineering'
                  AND fd.is_enabled = 1
                  AND fv.is_current = 1
                ORDER BY fd.sort_order, fd.id
                LIMIT 2
                """
            ).fetchall()

        self.assertIsNotNone(office)
        self.assertGreaterEqual(len(canals), 2)
        self.assertGreaterEqual(len(forms), 2)
        self.office_id = int(office["id"])
        self.canal_1_id = int(canals[0]["id"])
        self.canal_2_id = int(canals[1]["id"])
        self.form_1_id = int(forms[0]["form_version_id"])
        self.form_1_asset_type = forms[0]["asset_type"]
        self.form_2_id = int(forms[1]["form_version_id"])
        self.form_2_asset_type = forms[1]["asset_type"]

    def tearDown(self):
        database.DATA_DIR = self.original_data_dir
        database.DB_PATH = self.original_db_path
        gc.collect()
        self.temp_directory.cleanup()

    def _add_point(self, *, canal_id, form_version_id, asset_type, stake, code, revision_no=1, code_status="provisional", name=None):
        with database.get_connection() as connection:
            asset_cursor = connection.execute(
                """
                INSERT INTO engineering_assets (
                    project_id, asset_name, asset_type,
                    organization_unit_id, canal_unit_id,
                    business_code, single_stake_text, single_stake_value,
                    first_survey_batch_id, status,
                    revision_no, source_revision_no, code_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, 0, ?)
                """,
                (
                    self.project_id,
                    name or f"工程{stake}",
                    asset_type,
                    self.office_id,
                    canal_id,
                    code,
                    f"CH{int(stake // 1000)}+{int(stake % 1000):03d}",
                    float(stake),
                    self.batch_id,
                    revision_no,
                    code_status,
                ),
            )
            asset_id = int(asset_cursor.lastrowid)
            record_cursor = connection.execute(
                """
                INSERT INTO survey_records (
                    project_id, survey_batch_id, form_version_id,
                    record_type, organization_unit_id, canal_unit_id,
                    engineering_asset_id, business_code,
                    record_status, record_data_json,
                    revision_no, source_revision_no
                ) VALUES (?, ?, ?, 'engineering', ?, ?, ?, ?, 'completed', '{}', ?, 0)
                """,
                (
                    self.project_id,
                    self.batch_id,
                    form_version_id,
                    self.office_id,
                    canal_id,
                    asset_id,
                    code,
                    revision_no,
                ),
            )
            return asset_id, int(record_cursor.lastrowid)

    def test_late_upstream_record_reorders_without_revision_increment(self):
        a_id, _ = self._add_point(
            canal_id=self.canal_1_id,
            form_version_id=self.form_1_id,
            asset_type=self.form_1_asset_type,
            stake=100,
            code="1-01-03-02-001",
            revision_no=7,
            code_status="final",
            name="A",
        )
        b_id, _ = self._add_point(
            canal_id=self.canal_1_id,
            form_version_id=self.form_1_id,
            asset_type=self.form_1_asset_type,
            stake=300,
            code="1-01-03-02-002",
            revision_no=11,
            code_status="final",
            name="B",
        )
        c_id, _ = self._add_point(
            canal_id=self.canal_1_id,
            form_version_id=self.form_1_id,
            asset_type=self.form_1_asset_type,
            stake=200,
            code="1-01-03-02-099",
            revision_no=5,
            name="C",
        )

        with database.get_connection() as connection:
            before = {
                int(row["id"]): int(row["revision_no"])
                for row in connection.execute(
                    "SELECT id, revision_no FROM engineering_assets WHERE id IN (?, ?, ?)",
                    (a_id, b_id, c_id),
                ).fetchall()
            }

        preview = preview_engineering_business_code_renumber(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
        )
        self.assertTrue(preview.can_apply, preview.format_text())
        self.assertEqual(preview.total_assets, 3)
        self.assertEqual(preview.group_count, 1)

        result = renumber_engineering_business_codes(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
        )
        self.assertEqual(result.total_assets, 3)
        self.assertEqual(result.final_to_provisional_count, 2)

        with database.get_connection() as connection:
            rows = connection.execute(
                """
                SELECT ea.id, ea.asset_name, ea.business_code,
                       ea.code_status, ea.revision_no,
                       sr.business_code AS record_business_code,
                       sr.revision_no AS record_revision_no
                FROM engineering_assets AS ea
                JOIN survey_records AS sr ON sr.engineering_asset_id = ea.id
                WHERE ea.id IN (?, ?, ?)
                ORDER BY ea.single_stake_value
                """,
                (a_id, b_id, c_id),
            ).fetchall()

        self.assertEqual([row["asset_name"] for row in rows], ["A", "C", "B"])
        self.assertEqual(
            [row["business_code"].split("-")[-1] for row in rows],
            ["001", "002", "003"],
        )
        for row in rows:
            self.assertEqual(row["code_status"], "provisional")
            self.assertEqual(row["business_code"], row["record_business_code"])
            self.assertEqual(int(row["revision_no"]), before[int(row["id"])])

        second = renumber_engineering_business_codes(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
        )
        self.assertEqual(second.changed_code_count, 0)
        self.assertEqual(second.final_to_provisional_count, 0)

    def test_different_canals_restart_sequence(self):
        self._add_point(
            canal_id=self.canal_1_id,
            form_version_id=self.form_1_id,
            asset_type=self.form_1_asset_type,
            stake=100,
            code="1-01-03-02-077",
        )
        self._add_point(
            canal_id=self.canal_2_id,
            form_version_id=self.form_1_id,
            asset_type=self.form_1_asset_type,
            stake=150,
            code="1-01-03-02-077",
        )
        result = renumber_engineering_business_codes(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
        )
        self.assertEqual(result.group_count, 2)
        with database.get_connection() as connection:
            suffixes = [
                row["business_code"].split("-")[-1]
                for row in connection.execute(
                    "SELECT business_code FROM engineering_assets WHERE project_id = ? ORDER BY id",
                    (self.project_id,),
                ).fetchall()
            ]
        self.assertEqual(suffixes, ["001", "001"])

    def test_missing_stake_blocks_without_partial_write(self):
        good_id, _ = self._add_point(
            canal_id=self.canal_1_id,
            form_version_id=self.form_1_id,
            asset_type=self.form_1_asset_type,
            stake=100,
            code="1-01-03-02-099",
        )
        with database.get_connection() as connection:
            asset_cursor = connection.execute(
                """
                INSERT INTO engineering_assets (
                    project_id, asset_name, asset_type,
                    organization_unit_id, canal_unit_id,
                    business_code, first_survey_batch_id,
                    status, code_status
                ) VALUES (?, '缺桩号工程', ?, ?, ?, ?, ?, 'active', 'provisional')
                """,
                (
                    self.project_id,
                    self.form_1_asset_type,
                    self.office_id,
                    self.canal_1_id,
                    "1-01-03-02-088",
                    self.batch_id,
                ),
            )
            bad_id = int(asset_cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO survey_records (
                    project_id, survey_batch_id, form_version_id,
                    record_type, organization_unit_id, canal_unit_id,
                    engineering_asset_id, business_code,
                    record_status, record_data_json
                ) VALUES (?, ?, ?, 'engineering', ?, ?, ?, ?, 'completed', '{}')
                """,
                (
                    self.project_id,
                    self.batch_id,
                    self.form_1_id,
                    self.office_id,
                    self.canal_1_id,
                    bad_id,
                    "1-01-03-02-088",
                ),
            )

        preview = preview_engineering_business_code_renumber(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
        )
        self.assertFalse(preview.can_apply)
        self.assertTrue(any(item.code == "STAKE_MISSING" for item in preview.issues))

        with self.assertRaises(ValueError):
            renumber_engineering_business_codes(
                project_id=self.project_id,
                survey_batch_id=self.batch_id,
            )

        with database.get_connection() as connection:
            good = connection.execute(
                "SELECT business_code FROM engineering_assets WHERE id = ?",
                (good_id,),
            ).fetchone()
        self.assertTrue(good["business_code"].endswith("-099"))


if __name__ == "__main__":
    unittest.main()
