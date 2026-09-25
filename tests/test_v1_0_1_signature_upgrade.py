import gc
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import database


SIGNATURE_COLUMNS = (
    "surveyor_signatures",
    "water_office_manager_signature",
    "engineering_section_chief_signature",
    "department_head_signature",
)


class V101SignatureUpgradeTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_directory.name)

        self.original_data_dir = database.DATA_DIR
        self.original_db_path = database.DB_PATH

        database.DATA_DIR = self.temp_root / "local_data"
        database.DB_PATH = database.DATA_DIR / "legacy_v1_0_0.db"

        database.init_database()
        database.create_initial_forms()

        project = database.create_project(
            name="V1.0.0升级测试项目",
            short_name="升级测试",
        )
        self.project_id = int(project["project_id"])

        batch = database.create_survey_batch(
            project_id=self.project_id,
            batch_name="V1.0.0升级测试批次",
            batch_code="UPGRADE-100",
        )
        self.batch_id = int(batch["batch_id"])

        form_version = database.get_current_form_version("form_2_2")
        self.form_version_id = int(form_version["id"])

        with database.get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO survey_records (
                    project_id,
                    survey_batch_id,
                    form_version_id,
                    record_type,
                    business_code,
                    survey_date,
                    overall_grade,
                    survey_comment,
                    record_status,
                    record_data_json
                )
                VALUES (
                    ?, ?, ?, 'engineering',
                    ?, ?, ?, ?, 'draft', ?
                )
                """,
                (
                    self.project_id,
                    self.batch_id,
                    self.form_version_id,
                    "LEGACY-100-001",
                    "2026-09-18",
                    "B",
                    "V1.0.0既有调查意见",
                    json.dumps(
                        {"legacy_value": "必须保留"},
                        ensure_ascii=False,
                    ),
                ),
            )
            self.record_id = int(cursor.lastrowid)

            for column_name in SIGNATURE_COLUMNS:
                connection.execute(
                    "ALTER TABLE survey_records "
                    f"DROP COLUMN {column_name}"
                )

    def tearDown(self):
        database.DATA_DIR = self.original_data_dir
        database.DB_PATH = self.original_db_path
        gc.collect()
        time.sleep(0.05)
        self.temp_directory.cleanup()

    def _columns(self):
        with database.get_connection() as connection:
            return {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(survey_records)"
                ).fetchall()
            }

    def test_v100_database_upgrades_without_data_loss(self):
        before = self._columns()

        for column_name in SIGNATURE_COLUMNS:
            self.assertNotIn(column_name, before)

        database.init_database()

        after = self._columns()

        for column_name in SIGNATURE_COLUMNS:
            self.assertIn(column_name, after)

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    project_id,
                    survey_batch_id,
                    business_code,
                    survey_date,
                    overall_grade,
                    survey_comment,
                    record_status,
                    record_data_json,
                    surveyor_signatures,
                    water_office_manager_signature,
                    engineering_section_chief_signature,
                    department_head_signature
                FROM survey_records
                WHERE id = ?
                """,
                (self.record_id,),
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(int(row["project_id"]), self.project_id)
        self.assertEqual(int(row["survey_batch_id"]), self.batch_id)
        self.assertEqual(row["business_code"], "LEGACY-100-001")
        self.assertEqual(row["survey_date"], "2026-09-18")
        self.assertEqual(row["overall_grade"], "B")
        self.assertEqual(row["survey_comment"], "V1.0.0既有调查意见")
        self.assertEqual(row["record_status"], "draft")
        self.assertEqual(
            json.loads(row["record_data_json"]),
            {"legacy_value": "必须保留"},
        )

        for column_name in SIGNATURE_COLUMNS:
            self.assertIsNone(row[column_name])

    def test_migration_is_idempotent_and_fields_are_writable(self):
        database.init_database()
        database.init_database()

        with database.get_connection() as connection:
            connection.execute(
                """
                UPDATE survey_records
                SET
                    surveyor_signatures = ?,
                    water_office_manager_signature = ?,
                    engineering_section_chief_signature = ?,
                    department_head_signature = ?
                WHERE id = ?
                """,
                (
                    "张三、李四、王五",
                    "赵六",
                    "钱七",
                    "孙八",
                    self.record_id,
                ),
            )

            row = connection.execute(
                """
                SELECT
                    surveyor_signatures,
                    water_office_manager_signature,
                    engineering_section_chief_signature,
                    department_head_signature
                FROM survey_records
                WHERE id = ?
                """,
                (self.record_id,),
            ).fetchone()

        self.assertEqual(row["surveyor_signatures"], "张三、李四、王五")
        self.assertEqual(row["water_office_manager_signature"], "赵六")
        self.assertEqual(row["engineering_section_chief_signature"], "钱七")
        self.assertEqual(row["department_head_signature"], "孙八")


if __name__ == "__main__":
    unittest.main()
