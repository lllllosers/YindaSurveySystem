import gc
from hashlib import sha256
import json
import os
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
from services.survey_media import import_survey_media
from services.survey_result_package import (
    SurveyResultExportRequest,
    export_survey_result_package,
)
from services.survey_result_package_reader import (
    inspect_survey_result_package,
    load_survey_result_package,
)


class SurveyResultPackageReaderTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_directory.name)

        self.original_data_dir = database.DATA_DIR
        self.original_db_path = database.DB_PATH

        database.DATA_DIR = self.temp_root / "local_data"
        database.DB_PATH = database.DATA_DIR / "reader.db"

        initialize_application_database()

        with database.get_connection() as connection:
            project = connection.execute(
                """
                INSERT INTO projects (name, short_name, status)
                VALUES (?, ?, ?)
                """,
                ("2026项目", "2026", "active"),
            )
            self.project_id = int(project.lastrowid)

            batch = connection.execute(
                """
                INSERT INTO survey_batches (
                    project_id, batch_name, batch_code, status
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    self.project_id,
                    "2026批次",
                    "2026",
                    "active",
                ),
            )
            self.batch_id = int(batch.lastrowid)

            office = connection.execute(
                """
                SELECT id
                FROM organization_units
                WHERE master_key = 'ORG-D01-O03'
                """
            ).fetchone()

            canal = connection.execute(
                """
                SELECT id
                FROM canal_units
                WHERE master_key = 'CANAL-S001'
                """
            ).fetchone()

            form = connection.execute(
                """
                SELECT
                    fv.id AS form_version_id,
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

            self.office_id = int(office["id"])
            self.canal_id = int(canal["id"])
            self.form_version_id = int(form["form_version_id"])
            asset_type = str(form["asset_type"] or "test_asset")

            asset = connection.execute(
                """
                INSERT INTO engineering_assets (
                    project_id,
                    asset_name,
                    asset_type,
                    organization_unit_id,
                    canal_unit_id,
                    business_code,
                    first_survey_batch_id,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.project_id,
                    "测试工程",
                    asset_type,
                    self.office_id,
                    self.canal_id,
                    "1-03-03-01-001",
                    self.batch_id,
                    "active",
                ),
            )
            self.asset_id = int(asset.lastrowid)

            record = connection.execute(
                """
                INSERT INTO survey_records (
                    project_id,
                    survey_batch_id,
                    form_version_id,
                    record_type,
                    organization_unit_id,
                    canal_unit_id,
                    engineering_asset_id,
                    business_code,
                    survey_date,
                    overall_grade,
                    record_status,
                    record_data_json
                )
                VALUES (
                    ?, ?, ?, 'engineering',
                    ?, ?, ?, ?, ?,
                    ?, 'completed', ?
                )
                """,
                (
                    self.project_id,
                    self.batch_id,
                    self.form_version_id,
                    self.office_id,
                    self.canal_id,
                    self.asset_id,
                    "1-03-03-01-001",
                    "2026-09-17",
                    "B",
                    json.dumps(
                        {"field": "value"},
                        ensure_ascii=False,
                    ),
                ),
            )
            self.record_id = int(record.lastrowid)

            connection.execute(
                """
                UPDATE survey_records
                SET source_task_uid = ?
                WHERE id = ?
                """,
                (
                    "task-001",
                    self.record_id,
                ),
            )

            connection.execute(
                """
                INSERT INTO inspection_results (
                    survey_record_id,
                    item_code,
                    category,
                    item_name,
                    grade
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    self.record_id,
                    "A01",
                    "主体",
                    "测试分项",
                    "B",
                ),
            )

        source = self.temp_root / "现场照片.jpg"
        source.write_bytes(b"reader-test-media")

        self.media = import_survey_media(
            survey_record_id=self.record_id,
            source_file=source,
            media_role="overview",
            sequence_no=1,
        )

        self.package_path = self.temp_root / "成果.ydresult"

        export_survey_result_package(
            SurveyResultExportRequest(
                project_id=self.project_id,
                survey_batch_id=self.batch_id,
                survey_record_ids=(self.record_id,),
                output_path=self.package_path,
                result_name="测试调查成果",
            )
        )

    def tearDown(self):
        gc.collect()
        database.DATA_DIR = self.original_data_dir
        database.DB_PATH = self.original_db_path
        self.temp_directory.cleanup()

    def _rewrite_zip(self, mutate=None, extra_files=None):
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

        rewritten = (
            self.temp_root
            / f"rewritten_{os.urandom(4).hex()}.ydresult"
        )

        with zipfile.ZipFile(
            rewritten,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for path, content in files.items():
                archive.writestr(path, content)

        return rewritten

    def _rewrite_json_and_manifest(
        self,
        files,
        logical_path,
        document,
    ):
        payload = (
            json.dumps(
                document,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")

        files[logical_path] = payload

        manifest = json.loads(
            files["manifest.json"].decode("utf-8")
        )

        for entry in manifest["files"]:
            if entry["path"] == logical_path:
                entry["size"] = len(payload)
                entry["sha256"] = sha256(payload).hexdigest()

        files["manifest.json"] = (
            json.dumps(
                manifest,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")

    def test_valid_package_can_be_inspected_and_loaded(self):
        inspection = inspect_survey_result_package(
            self.package_path
        )

        self.assertTrue(
            inspection.valid,
            inspection.format_text(),
        )
        self.assertEqual(len(inspection.engineering_assets), 1)
        self.assertEqual(len(inspection.survey_records), 1)
        self.assertEqual(len(inspection.inspection_results), 1)
        self.assertEqual(len(inspection.survey_media), 1)

        loaded = load_survey_result_package(
            self.package_path
        )
        self.assertEqual(
            loaded.result["result_name"],
            "测试调查成果",
        )
        self.assertEqual(
            loaded.result["source_task_uids"],
            [
                "task-001",
            ],
        )

    def test_tampered_media_is_rejected(self):
        media_path = (
            f"media/{self.media['media_uid']}.jpg"
        )

        def mutate(files):
            files[media_path] = b"tampered"

        tampered = self._rewrite_zip(
            mutate=mutate
        )

        inspection = inspect_survey_result_package(
            tampered
        )
        codes = {
            issue.code
            for issue in inspection.issues
        }

        self.assertIn("HASH_MISMATCH", codes)

    def test_result_uid_mismatch_is_rejected(self):
        def mutate(files):
            document = json.loads(
                files["result.json"].decode("utf-8")
            )
            document["result_uid"] = "different-result"
            self._rewrite_json_and_manifest(
                files,
                "result.json",
                document,
            )

        tampered = self._rewrite_zip(
            mutate=mutate
        )

        inspection = inspect_survey_result_package(
            tampered
        )
        codes = {
            issue.code
            for issue in inspection.issues
        }

        self.assertIn(
            "RESULT_UID_MISMATCH",
            codes,
        )

    def test_missing_asset_reference_is_rejected(self):
        def mutate(files):
            self._rewrite_json_and_manifest(
                files,
                "data/engineering_assets.json",
                {"items": []},
            )

        tampered = self._rewrite_zip(
            mutate=mutate
        )

        inspection = inspect_survey_result_package(
            tampered
        )
        codes = {
            issue.code
            for issue in inspection.issues
        }

        self.assertIn(
            "RESULT_RECORD_ASSET_MISSING",
            codes,
        )

    def test_media_metadata_hash_mismatch_is_rejected(self):
        def mutate(files):
            document = json.loads(
                files[
                    "data/survey_media.json"
                ].decode("utf-8")
            )
            document["items"][0]["file_sha256"] = "0" * 64

            self._rewrite_json_and_manifest(
                files,
                "data/survey_media.json",
                document,
            )

        tampered = self._rewrite_zip(
            mutate=mutate
        )

        inspection = inspect_survey_result_package(
            tampered
        )
        codes = {
            issue.code
            for issue in inspection.issues
        }

        self.assertIn(
            "RESULT_MEDIA_HASH_MISMATCH",
            codes,
        )

    def test_untracked_file_is_rejected(self):
        tampered = self._rewrite_zip(
            extra_files={
                "extra.txt": b"x",
            }
        )

        inspection = inspect_survey_result_package(
            tampered
        )
        codes = {
            issue.code
            for issue in inspection.issues
        }

        self.assertIn(
            "UNTRACKED_FILE",
            codes,
        )


if __name__ == "__main__":
    unittest.main()
