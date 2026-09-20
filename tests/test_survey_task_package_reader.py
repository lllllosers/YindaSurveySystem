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
from services.survey_task_package_reader import (
    inspect_survey_task_package,
    load_survey_task_package,
)


class SurveyTaskPackageReaderTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_directory.name)
        self.original_data_dir = database.DATA_DIR
        self.original_db_path = database.DB_PATH
        database.DATA_DIR = self.temp_root / "local_data"
        database.DB_PATH = database.DATA_DIR / "task_reader.db"
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

        self.package_path = self.temp_root / "任务.ydtask"
        export_survey_task_package(
            SurveyTaskExportRequest(
                project_id=self.project_id,
                survey_batch_id=self.batch_id,
                organization_unit_id=self.office_id,
                management_scope_uids=self.scope_uids,
                task_name="通远水管所调查任务",
                output_path=self.package_path,
                notes="读取测试",
            )
        )

    def tearDown(self):
        gc.collect()
        database.DATA_DIR = self.original_data_dir
        database.DB_PATH = self.original_db_path
        self.temp_directory.cleanup()

    def _rewrite_json_payload(self, files, path, document):
        payload = (
            json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n"
        ).encode("utf-8")
        files[path] = payload
        manifest = json.loads(files["manifest.json"].decode("utf-8"))
        for entry in manifest["files"]:
            if entry["path"] == path:
                entry["size"] = len(payload)
                entry["sha256"] = sha256(payload).hexdigest()
                break
        files["manifest.json"] = (
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n"
        ).encode("utf-8")

    def _rewrite_zip(self, *, mutate=None, extra_files=None):
        with zipfile.ZipFile(self.package_path, "r") as archive:
            files = {
                info.filename: archive.read(info.filename)
                for info in archive.infolist()
                if not info.is_dir()
            }
        if mutate:
            mutate(files)
        if extra_files:
            files.update(extra_files)
        rewritten = self.temp_root / "rewritten.ydtask"
        with zipfile.ZipFile(rewritten, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path, content in files.items():
                archive.writestr(path, content)
        return rewritten

    def test_valid_package_can_be_inspected_and_loaded(self):
        inspection = inspect_survey_task_package(self.package_path)
        self.assertTrue(inspection.valid, inspection.format_text())
        self.assertEqual(len(inspection.organizations), 2)
        self.assertGreaterEqual(len(inspection.canals), 3)
        self.assertEqual(len(inspection.management_scopes), 2)
        self.assertGreater(len(inspection.forms), 0)
        contents = load_survey_task_package(self.package_path)
        self.assertEqual(contents.task["task_schema_version"], "3.0")
        self.assertEqual(len(contents.management_scopes), 2)

    def test_tampered_payload_hash_is_rejected(self):
        def mutate(files):
            files["task.json"] += b" "
        inspection = inspect_survey_task_package(
            self._rewrite_zip(mutate=mutate)
        )
        self.assertIn("HASH_MISMATCH", {issue.code for issue in inspection.issues})

    def test_untracked_file_is_rejected(self):
        inspection = inspect_survey_task_package(
            self._rewrite_zip(extra_files={"extra.txt": b"x"})
        )
        self.assertIn("UNTRACKED_FILE", {issue.code for issue in inspection.issues})

    def test_path_traversal_member_is_rejected(self):
        inspection = inspect_survey_task_package(
            self._rewrite_zip(extra_files={"../escape.txt": b"x"})
        )
        self.assertIn("UNSAFE_PATH", {issue.code for issue in inspection.issues})

    def test_old_task_schema_is_rejected(self):
        def mutate(files):
            task = json.loads(files["task.json"].decode("utf-8"))
            task["task_schema_version"] = "1.0"
            self._rewrite_json_payload(files, "task.json", task)
            manifest = json.loads(files["manifest.json"].decode("utf-8"))
            manifest["task_schema_version"] = "1.0"
            files["manifest.json"] = (
                json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
                + "\n"
            ).encode("utf-8")

        inspection = inspect_survey_task_package(
            self._rewrite_zip(mutate=mutate)
        )
        codes = {issue.code for issue in inspection.issues}
        self.assertIn("TASK_SCHEMA_VERSION_UNSUPPORTED", codes)
        self.assertFalse(inspection.valid)

    def test_scope_owner_mismatch_is_rejected(self):
        def mutate(files):
            path = "reference/canal_management_scopes.json"
            scopes = json.loads(files[path].decode("utf-8"))
            scopes["items"][0]["organization_unit_uid"] = "wrong-owner"
            self._rewrite_json_payload(files, path, scopes)

        inspection = inspect_survey_task_package(
            self._rewrite_zip(mutate=mutate)
        )
        self.assertIn(
            "REFERENCE_SCOPE_OWNER_MISMATCH",
            {issue.code for issue in inspection.issues},
        )

    def test_legacy_canal_owner_field_is_rejected(self):
        def mutate(files):
            path = "reference/canal_units.json"
            canals = json.loads(files[path].decode("utf-8"))
            canals["items"][0]["management_organization_uid"] = "legacy-owner"
            self._rewrite_json_payload(files, path, canals)

        inspection = inspect_survey_task_package(
            self._rewrite_zip(mutate=mutate)
        )
        self.assertIn(
            "REFERENCE_CANAL_LEGACY_OWNER_FIELD",
            {issue.code for issue in inspection.issues},
        )

    def test_v2_task_without_lineage_is_still_supported(self):
        def mutate(files):
            task = json.loads(
                files["task.json"].decode("utf-8")
            )
            task["task_schema_version"] = "2.0"
            task.pop("lineage", None)
            self._rewrite_json_payload(
                files,
                "task.json",
                task,
            )

            manifest = json.loads(
                files["manifest.json"].decode("utf-8")
            )
            manifest["task_schema_version"] = "2.0"
            manifest.pop("parent_task_uid", None)
            manifest.pop("root_task_uid", None)
            manifest.pop("task_depth", None)
            files["manifest.json"] = (
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            ).encode("utf-8")

        package = self._rewrite_zip(
            mutate=mutate
        )

        inspection = inspect_survey_task_package(
            package
        )
        self.assertTrue(
            inspection.valid,
            inspection.format_text(),
        )

        contents = load_survey_task_package(
            package
        )
        self.assertEqual(
            contents.task["task_schema_version"],
            "2.0",
        )

    def test_v3_invalid_lineage_is_rejected(self):
        def mutate(files):
            task = json.loads(
                files["task.json"].decode("utf-8")
            )
            task["lineage"]["root_task_uid"] = "wrong-root"
            self._rewrite_json_payload(
                files,
                "task.json",
                task,
            )

        inspection = inspect_survey_task_package(
            self._rewrite_zip(
                mutate=mutate
            )
        )

        self.assertFalse(
            inspection.valid
        )
        self.assertIn(
            "TASK_LINEAGE_INVALID",
            {
                issue.code
                for issue in inspection.issues
            },
        )


if __name__ == "__main__":
    unittest.main()
