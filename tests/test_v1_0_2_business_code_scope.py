import gc
import sqlite3
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
from services.survey_result_import import (
    _insert_record,
    _update_asset_from_package,
    _update_record_from_package,
)
from services.survey_result_import_preflight import (
    _asset_signature,
    _canonical_json,
    _record_signature,
)


class V102BusinessCodeScopeTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_directory.name)
        self.original_data_dir = database.DATA_DIR
        self.original_db_path = database.DB_PATH
        database.DATA_DIR = self.temp_root / "local_data"
        database.DB_PATH = database.DATA_DIR / "stage3a.db"
        initialize_application_database()

        project = database.create_project(
            name="V1.0.2编号作用域测试",
            short_name="编号作用域",
        )
        self.project_id = int(project["project_id"])
        batch = database.create_survey_batch(
            project_id=self.project_id,
            batch_name="编号作用域批次",
            batch_code="CODE-SCOPE-102",
        )
        self.batch_id = int(batch["batch_id"])

        with database.get_connection() as connection:
            office = connection.execute(
                """
                SELECT id, organization_unit_uid
                FROM organization_units
                WHERE unit_type = 'water_office' AND status = 'active'
                ORDER BY id LIMIT 1
                """
            ).fetchone()
            canals = connection.execute(
                """
                SELECT id, canal_unit_uid
                FROM canal_units
                WHERE status = 'active'
                ORDER BY id LIMIT 2
                """
            ).fetchall()
            form = connection.execute(
                """
                SELECT fv.id AS form_version_id,
                       fv.version_code,
                       fd.form_code,
                       fd.asset_type
                FROM form_definitions AS fd
                JOIN form_versions AS fv
                  ON fv.form_definition_id = fd.id
                WHERE fd.series = 'series_2'
                  AND fd.record_type = 'engineering'
                  AND fd.is_enabled = 1
                  AND fv.is_current = 1
                ORDER BY fd.sort_order, fd.id
                LIMIT 1
                """
            ).fetchone()

        self.assertIsNotNone(office)
        self.assertGreaterEqual(len(canals), 2)
        self.assertIsNotNone(form)
        self.office_id = int(office["id"])
        self.office_uid = office["organization_unit_uid"]
        self.canal_1_id = int(canals[0]["id"])
        self.canal_1_uid = canals[0]["canal_unit_uid"]
        self.canal_2_id = int(canals[1]["id"])
        self.form_version_id = int(form["form_version_id"])
        self.form_code = form["form_code"]
        self.form_version_code = form["version_code"]
        self.asset_type = form["asset_type"] or "test_asset"

    def tearDown(self):
        database.DATA_DIR = self.original_data_dir
        database.DB_PATH = self.original_db_path
        gc.collect()
        self.temp_directory.cleanup()

    def _insert_asset(self, *, canal_id, business_code, code_status, name,
                      single_stake_value=None):
        with database.get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO engineering_assets (
                    project_id, asset_name, asset_type,
                    organization_unit_id, canal_unit_id,
                    business_code, first_survey_batch_id,
                    status, code_status,
                    single_stake_text, single_stake_value
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    self.project_id, name, self.asset_type,
                    self.office_id, canal_id, business_code,
                    self.batch_id, code_status,
                    "CH0+100" if single_stake_value is not None else None,
                    single_stake_value,
                ),
            )
            return int(cursor.lastrowid)

    def test_final_number_is_unique_only_inside_specific_canal(self):
        code = "1-01-03-02-001"
        self._insert_asset(
            canal_id=self.canal_1_id,
            business_code=code,
            code_status="final",
            name="一支渠正式工程",
        )
        self._insert_asset(
            canal_id=self.canal_2_id,
            business_code=code,
            code_status="final",
            name="二支渠同号工程",
        )
        self._insert_asset(
            canal_id=self.canal_1_id,
            business_code=code,
            code_status="provisional",
            name="一支渠暂编同号工程",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_asset(
                canal_id=self.canal_1_id,
                business_code=code,
                code_status="final",
                name="一支渠重复正式编号",
            )

        with database.get_connection() as connection:
            table_sql = str(connection.execute(
                """
                SELECT sql FROM sqlite_master
                WHERE type='table' AND name='engineering_assets'
                """
            ).fetchone()["sql"] or "")
            indexes = {
                row["name"]
                for row in connection.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='index' AND tbl_name='engineering_assets'
                    """
                ).fetchall()
            }
        compact = "".join(table_sql.lower().split())
        self.assertNotIn("unique(project_id,business_code)", compact)
        self.assertIn(
            "uq_engineering_assets_final_business_code_scope",
            indexes,
        )

    def test_business_code_is_not_business_revision_content(self):
        asset_a = {
            "project_uid": "p",
            "asset_name": "工程A",
            "asset_type": "sluice",
            "organization_unit_uid": "o",
            "canal_unit_uid": "c",
            "business_code": "1-01-03-02-001",
            "code_scheme_version": "V1",
            "single_stake_text": "CH0+100",
            "single_stake_value": 100.0,
            "status": "active",
        }
        asset_b = dict(asset_a)
        asset_b["business_code"] = "1-01-03-02-009"
        asset_b["code_scheme_version"] = "V9"
        self.assertEqual(
            _canonical_json(_asset_signature(asset_a)),
            _canonical_json(_asset_signature(asset_b)),
        )

        record_a = {
            "source_task_uid": "t",
            "source_management_scope_uid": "s",
            "project_uid": "p",
            "survey_batch_uid": "b",
            "form": {"form_code": "form_2_2", "version_code": "V1"},
            "record_type": "engineering",
            "organization_unit_uid": "o",
            "canal_unit_uid": "c",
            "engineering_asset_uid": "a",
            "business_code": "1-01-03-02-001",
            "survey_date": "2026-09-20",
            "overall_grade": "B",
            "record_status": "completed",
            "record_data": {"demo": 1},
        }
        record_b = dict(record_a)
        record_b["business_code"] = "1-01-03-02-009"
        self.assertEqual(
            _canonical_json(_record_signature(record_a)),
            _canonical_json(_record_signature(record_b)),
        )

    def test_received_update_preserves_receiver_business_code(self):
        local_code = "1-01-03-02-001"
        incoming_code = "1-01-03-02-099"
        asset_id = self._insert_asset(
            canal_id=self.canal_1_id,
            business_code=local_code,
            code_status="final",
            name="接收方工程",
            single_stake_value=100.0,
        )

        with database.get_connection() as connection:
            asset_uid = connection.execute(
                "SELECT engineering_asset_uid FROM engineering_assets WHERE id=?",
                (asset_id,),
            ).fetchone()["engineering_asset_uid"]
            record_cursor = connection.execute(
                """
                INSERT INTO survey_records (
                    project_id, survey_batch_id, form_version_id,
                    record_type, organization_unit_id, canal_unit_id,
                    engineering_asset_id, business_code,
                    survey_date, overall_grade, record_status,
                    record_data_json, revision_no, source_revision_no
                )
                VALUES (?, ?, ?, 'engineering', ?, ?, ?, ?, ?, ?,
                        'completed', '{}', 1, 1)
                """,
                (
                    self.project_id, self.batch_id, self.form_version_id,
                    self.office_id, self.canal_1_id, asset_id,
                    local_code, "2026-09-20", "B",
                ),
            )
            record_id = int(record_cursor.lastrowid)

            _update_asset_from_package(
                connection,
                {
                    "asset_name": "下级修订工程",
                    "business_code": incoming_code,
                    "code_scheme_version": "V9",
                    "single_stake_text": "CH0+200",
                    "single_stake_value": 200.0,
                    "start_stake_text": None,
                    "start_stake_value": None,
                    "end_stake_text": None,
                    "end_stake_value": None,
                    "status": "active",
                    "notes": "下级修订",
                    "revision_no": 2,
                    "updated_at": "2026-09-20 10:00:00",
                },
                asset_id=asset_id,
            )
            _update_record_from_package(
                connection,
                {
                    "business_code": incoming_code,
                    "survey_date": "2026-09-20",
                    "overall_grade": "C",
                    "survey_comment": "下级更正",
                    "surveyor_signatures": None,
                    "water_office_manager_signature": None,
                    "engineering_section_chief_signature": None,
                    "department_head_signature": None,
                    "record_status": "completed",
                    "record_data": {"demo": 2},
                    "void_reason": None,
                    "revision_no": 2,
                    "updated_at": "2026-09-20 10:00:00",
                },
                record_id=record_id,
            )

            updated_asset = connection.execute(
                """
                SELECT business_code, code_scheme_version, code_status,
                       revision_no, source_revision_no, single_stake_value
                FROM engineering_assets WHERE id=?
                """,
                (asset_id,),
            ).fetchone()
            updated_record = connection.execute(
                """
                SELECT business_code, revision_no, source_revision_no,
                       overall_grade
                FROM survey_records WHERE id=?
                """,
                (record_id,),
            ).fetchone()

            inserted_record_id = _insert_record(
                connection,
                {
                    "survey_record_uid": "stage3a-new-record-uid",
                    "source_task_uid": None,
                    "source_management_scope_uid": None,
                    "form": {
                        "form_code": self.form_code,
                        "version_code": self.form_version_code,
                    },
                    "record_type": "engineering",
                    "organization_unit_uid": self.office_uid,
                    "canal_unit_uid": self.canal_1_uid,
                    "engineering_asset_uid": asset_uid,
                    "business_code": incoming_code,
                    "survey_date": "2026-09-20",
                    "overall_grade": "B",
                    "survey_comment": None,
                    "record_status": "completed",
                    "record_data": {},
                    "void_reason": None,
                    "revision_no": 1,
                    "created_at": "2026-09-20 11:00:00",
                    "updated_at": "2026-09-20 11:00:00",
                },
                project_id=self.project_id,
                batch_id=self.batch_id,
                asset_id=asset_id,
            )
            inserted_record = connection.execute(
                "SELECT business_code FROM survey_records WHERE id=?",
                (inserted_record_id,),
            ).fetchone()

        self.assertEqual(updated_asset["business_code"], local_code)
        self.assertEqual(updated_asset["code_scheme_version"], "V1")
        self.assertEqual(updated_asset["code_status"], "provisional")
        self.assertEqual(int(updated_asset["revision_no"]), 2)
        self.assertEqual(int(updated_asset["source_revision_no"]), 2)
        self.assertAlmostEqual(float(updated_asset["single_stake_value"]), 200.0)
        self.assertEqual(updated_record["business_code"], local_code)
        self.assertEqual(int(updated_record["revision_no"]), 2)
        self.assertEqual(int(updated_record["source_revision_no"]), 2)
        self.assertEqual(updated_record["overall_grade"], "C")
        self.assertEqual(inserted_record["business_code"], local_code)

    def test_business_code_query_can_be_scoped_to_specific_canal(self):
        code_1 = "1-01-03-02-001"
        code_2 = "1-01-03-02-002"
        self._insert_asset(
            canal_id=self.canal_1_id,
            business_code=code_1,
            code_status="provisional",
            name="渠1工程1",
        )
        self._insert_asset(
            canal_id=self.canal_1_id,
            business_code=code_2,
            code_status="provisional",
            name="渠1工程2",
        )
        self._insert_asset(
            canal_id=self.canal_2_id,
            business_code=code_1,
            code_status="provisional",
            name="渠2工程1",
        )
        self.assertEqual(
            database.get_engineering_business_codes(
                self.project_id,
                canal_unit_id=self.canal_1_id,
            ),
            [code_1, code_2],
        )
        self.assertEqual(
            database.get_engineering_business_codes(
                self.project_id,
                canal_unit_id=self.canal_2_id,
            ),
            [code_1],
        )


if __name__ == "__main__":
    unittest.main()
