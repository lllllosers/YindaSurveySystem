import gc
from hashlib import sha256
import json
import sys
import tempfile
import unittest
from pathlib import Path
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import database
from services.application_bootstrap import initialize_application_database
from services.survey_task_package import (
    SurveyTaskExportRequest,
    export_survey_task_package,
)


class SurveyTaskPackageTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_directory.name)
        self.original_data_dir = database.DATA_DIR
        self.original_db_path = database.DB_PATH
        database.DATA_DIR = self.temp_root / "local_data"
        database.DB_PATH = database.DATA_DIR / "task_package.db"
        initialize_application_database()

        with database.get_connection() as connection:
            project = connection.execute(
                "INSERT INTO projects (name, short_name, status) VALUES (?, ?, 'active')",
                ("2026年引大入秦灌区现状调查", "2026现状调查"),
            )
            self.project_id = int(project.lastrowid)
            batch = connection.execute(
                """
                INSERT INTO survey_batches (
                    project_id, batch_name, batch_code, status
                ) VALUES (?, ?, ?, 'active')
                """,
                (self.project_id, "2026年调查批次", "2026"),
            )
            self.batch_id = int(batch.lastrowid)
            office = connection.execute(
                "SELECT id FROM organization_units WHERE master_key = ?",
                ("ORG-D01-O03",),
            ).fetchone()
            self.office_id = int(office["id"])
            rows = connection.execute(
                """
                SELECT management_scope_uid
                FROM canal_management_scopes
                WHERE master_key IN (
                    'CMS-CANAL-S001-ORG-D01-O03',
                    'CMS-CANAL-S002-ORG-D01-O03'
                )
                ORDER BY sort_order, id
                """
            ).fetchall()
            self.scope_uids = tuple(row["management_scope_uid"] for row in rows)

        self.assertEqual(len(self.scope_uids), 2)

    def tearDown(self):
        gc.collect()
        database.DATA_DIR = self.original_data_dir
        database.DB_PATH = self.original_db_path
        self.temp_directory.cleanup()

    def _export(self, filename="通远水管所任务.ydtask", scope_uids=None):
        return export_survey_task_package(
            SurveyTaskExportRequest(
                project_id=self.project_id,
                survey_batch_id=self.batch_id,
                organization_unit_id=self.office_id,
                management_scope_uids=tuple(
                    self.scope_uids if scope_uids is None else scope_uids
                ),
                task_name="通远水管所调查任务",
                notes="分管范围调查任务",
                output_path=self.temp_root / filename,
            )
        )

    def test_exports_new_scope_package_structure(self):
        result = self._export()
        with zipfile.ZipFile(result.output_path, "r") as archive:
            names = set(archive.namelist())
        self.assertEqual(
            names,
            {
                "manifest.json",
                "task.json",
                "reference/organization_units.json",
                "reference/canal_units.json",
                "reference/canal_management_scopes.json",
                "reference/forms.json",
            },
        )
        self.assertEqual(result.selected_management_scope_count, 2)

    def test_manifest_hashes_every_payload_file(self):
        result = self._export()
        with zipfile.ZipFile(result.output_path, "r") as archive:
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["package_kind"], "survey_task")
            self.assertEqual(manifest["task_schema_version"], "2.0")
            for entry in manifest["files"]:
                content = archive.read(entry["path"])
                self.assertEqual(len(content), entry["size"])
                self.assertEqual(sha256(content).hexdigest(), entry["sha256"])

    def test_task_uses_scope_uids_and_physical_canals_have_no_owner(self):
        result = self._export()
        with zipfile.ZipFile(result.output_path, "r") as archive:
            task = json.loads(archive.read("task.json"))
            canals = json.loads(
                archive.read("reference/canal_units.json")
            )["items"]
            scopes = json.loads(
                archive.read("reference/canal_management_scopes.json")
            )["items"]

        self.assertEqual(task["task_schema_version"], "2.0")
        self.assertNotIn("selected_canal_uids", task["scope"])
        self.assertEqual(
            set(task["scope"]["selected_management_scope_uids"]),
            set(self.scope_uids),
        )
        for item in canals:
            self.assertNotIn("management_organization_uid", item)
        self.assertEqual(
            {item["management_scope_uid"] for item in scopes},
            set(self.scope_uids),
        )

    def test_reference_canals_include_selected_ancestors(self):
        result = self._export(scope_uids=self.scope_uids[:1])
        with zipfile.ZipFile(result.output_path, "r") as archive:
            canals = json.loads(
                archive.read("reference/canal_units.json")
            )["items"]
        names = {item["name"] for item in canals}
        self.assertIn("通远支渠", names)
        self.assertIn("总干渠", names)
        self.assertEqual(result.selected_management_scope_count, 1)
        self.assertEqual(result.reference_canal_count, 2)

    def test_cannot_export_scope_of_another_office(self):
        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT management_scope_uid
                FROM canal_management_scopes
                WHERE organization_unit_id != ? AND status = 'active'
                ORDER BY id LIMIT 1
                """,
                (self.office_id,),
            ).fetchone()
        self.assertIsNotNone(row)
        with self.assertRaises(ValueError) as context:
            self._export(scope_uids=(row["management_scope_uid"],))
        self.assertIn("不属于当前管理单位", str(context.exception))

    def test_existing_target_is_not_overwritten(self):
        result = self._export()
        before = result.output_path.read_bytes()
        with self.assertRaises(FileExistsError):
            self._export()
        self.assertEqual(before, result.output_path.read_bytes())

    def test_missing_extension_is_added(self):
        result = self._export(filename="任务包")
        self.assertEqual(result.output_path.name, "任务包.ydtask")


if __name__ == "__main__":
    unittest.main()
