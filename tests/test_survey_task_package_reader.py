import gc
from hashlib import sha256
import json
import sys
import tempfile
import unittest
from pathlib import Path
import zipfile


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
from services.survey_task_package import (
    SurveyTaskExportRequest,
    export_survey_task_package,
)
from services.survey_task_package_reader import (
    inspect_survey_task_package,
    load_survey_task_package,
)


class SurveyTaskPackageReaderTestCase(
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
            / "task_reader.db"
        )

        initialize_application_database()

        with database.get_connection() as connection:
            project = connection.execute(
                """
                INSERT INTO projects (
                    name,
                    short_name,
                    status
                )
                VALUES (?, ?, ?)
                """,
                (
                    "2026年引大入秦灌区现状调查",
                    "2026现状调查",
                    "active",
                ),
            )

            self.project_id = int(
                project.lastrowid
            )

            batch = connection.execute(
                """
                INSERT INTO survey_batches (
                    project_id,
                    batch_name,
                    batch_code,
                    status
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    self.project_id,
                    "2026年调查批次",
                    "2026",
                    "active",
                ),
            )

            self.batch_id = int(
                batch.lastrowid
            )

            office = connection.execute(
                """
                SELECT id
                FROM organization_units
                WHERE master_key = ?
                """,
                ("ORG-D01-O03",),
            ).fetchone()

            self.office_id = int(
                office["id"]
            )

            canals = connection.execute(
                """
                SELECT id
                FROM canal_units
                WHERE master_key IN (
                    'CANAL-S001',
                    'CANAL-S002'
                )
                ORDER BY sort_order
                """
            ).fetchall()

            self.canal_ids = tuple(
                int(row["id"])
                for row in canals
            )

        self.package_path = (
            self.temp_root
            / "任务.ydtask"
        )

        export_survey_task_package(
            SurveyTaskExportRequest(
                project_id=(
                    self.project_id
                ),
                survey_batch_id=(
                    self.batch_id
                ),
                organization_unit_id=(
                    self.office_id
                ),
                canal_ids=(
                    self.canal_ids
                ),
                task_name=(
                    "通远水管所调查任务"
                ),
                output_path=(
                    self.package_path
                ),
                notes="读取测试",
            )
        )

    def tearDown(self):
        gc.collect()

        database.DATA_DIR = (
            self.original_data_dir
        )
        database.DB_PATH = (
            self.original_db_path
        )

        self.temp_directory.cleanup()

    def _rewrite_zip(
        self,
        *,
        mutate=None,
        extra_files=None,
    ):
        with zipfile.ZipFile(
            self.package_path,
            "r",
        ) as archive:
            files = {
                info.filename:
                archive.read(
                    info.filename
                )
                for info in archive.infolist()
                if not info.is_dir()
            }

        if mutate:
            mutate(files)

        if extra_files:
            files.update(
                extra_files
            )

        rewritten = (
            self.temp_root
            / "rewritten.ydtask"
        )

        with zipfile.ZipFile(
            rewritten,
            "w",
            compression=(
                zipfile.ZIP_DEFLATED
            ),
        ) as archive:
            for path, content in (
                files.items()
            ):
                archive.writestr(
                    path,
                    content,
                )

        return rewritten

    def test_valid_package_can_be_inspected_and_loaded(
        self,
    ):
        inspection = (
            inspect_survey_task_package(
                self.package_path
            )
        )

        self.assertTrue(
            inspection.valid
        )
        self.assertEqual(
            inspection.error_count,
            0,
        )
        self.assertEqual(
            len(
                inspection.organizations
            ),
            2,
        )
        self.assertGreaterEqual(
            len(
                inspection.canals
            ),
            3,
        )
        self.assertGreater(
            len(
                inspection.forms
            ),
            0,
        )

        contents = (
            load_survey_task_package(
                self.package_path
            )
        )

        self.assertEqual(
            contents.task[
                "task_name"
            ],
            "通远水管所调查任务",
        )

    def test_tampered_payload_hash_is_rejected(
        self,
    ):
        def mutate(files):
            files[
                "task.json"
            ] = (
                files[
                    "task.json"
                ]
                + b" "
            )

        tampered = (
            self._rewrite_zip(
                mutate=mutate
            )
        )

        inspection = (
            inspect_survey_task_package(
                tampered
            )
        )

        codes = {
            issue.code
            for issue in inspection.issues
        }

        self.assertIn(
            "HASH_MISMATCH",
            codes,
        )
        self.assertFalse(
            inspection.valid
        )

    def test_untracked_file_is_rejected(
        self,
    ):
        tampered = (
            self._rewrite_zip(
                extra_files={
                    "extra.txt": b"x",
                }
            )
        )

        inspection = (
            inspect_survey_task_package(
                tampered
            )
        )

        codes = {
            issue.code
            for issue in inspection.issues
        }

        self.assertIn(
            "UNTRACKED_FILE",
            codes,
        )

    def test_path_traversal_member_is_rejected(
        self,
    ):
        tampered = (
            self._rewrite_zip(
                extra_files={
                    "../escape.txt": b"x",
                }
            )
        )

        inspection = (
            inspect_survey_task_package(
                tampered
            )
        )

        codes = {
            issue.code
            for issue in inspection.issues
        }

        self.assertIn(
            "UNSAFE_PATH",
            codes,
        )

    def test_task_uid_mismatch_is_rejected_even_with_valid_hash(
        self,
    ):
        def mutate(files):
            manifest = json.loads(
                files[
                    "manifest.json"
                ].decode("utf-8")
            )

            task = json.loads(
                files[
                    "task.json"
                ].decode("utf-8")
            )

            task[
                "task_uid"
            ] = "different-task"

            task_bytes = (
                json.dumps(
                    task,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            ).encode("utf-8")

            files[
                "task.json"
            ] = task_bytes

            for entry in manifest[
                "files"
            ]:
                if (
                    entry["path"]
                    == "task.json"
                ):
                    entry["size"] = (
                        len(task_bytes)
                    )

                    entry["sha256"] = (
                        sha256(
                            task_bytes
                        ).hexdigest()
                    )

            files[
                "manifest.json"
            ] = (
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            ).encode("utf-8")

        tampered = (
            self._rewrite_zip(
                mutate=mutate
            )
        )

        inspection = (
            inspect_survey_task_package(
                tampered
            )
        )

        codes = {
            issue.code
            for issue in inspection.issues
        }

        self.assertIn(
            "TASK_UID_MISMATCH",
            codes,
        )

    def test_selected_canal_owner_mismatch_is_rejected(
        self,
    ):
        def mutate(files):
            manifest = json.loads(
                files[
                    "manifest.json"
                ].decode("utf-8")
            )

            canals_doc = json.loads(
                files[
                    (
                        "reference/"
                        "canal_units.json"
                    )
                ].decode("utf-8")
            )

            task = json.loads(
                files[
                    "task.json"
                ].decode("utf-8")
            )

            selected_uid = (
                task[
                    "scope"
                ][
                    "selected_canal_uids"
                ][0]
            )

            for item in canals_doc[
                "items"
            ]:
                if (
                    item["canal_uid"]
                    == selected_uid
                ):
                    item[
                        "management_organization_uid"
                    ] = "wrong-owner"

            canal_bytes = (
                json.dumps(
                    canals_doc,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            ).encode("utf-8")

            files[
                (
                    "reference/"
                    "canal_units.json"
                )
            ] = canal_bytes

            for entry in manifest[
                "files"
            ]:
                if (
                    entry["path"]
                    == (
                        "reference/"
                        "canal_units.json"
                    )
                ):
                    entry["size"] = (
                        len(canal_bytes)
                    )

                    entry["sha256"] = (
                        sha256(
                            canal_bytes
                        ).hexdigest()
                    )

            files[
                "manifest.json"
            ] = (
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            ).encode("utf-8")

        tampered = (
            self._rewrite_zip(
                mutate=mutate
            )
        )

        inspection = (
            inspect_survey_task_package(
                tampered
            )
        )

        codes = {
            issue.code
            for issue in inspection.issues
        }

        self.assertIn(
            "TASK_CANAL_OWNER_MISMATCH",
            codes,
        )

    def test_non_zip_is_rejected_without_exception(
        self,
    ):
        bad_path = (
            self.temp_root
            / "bad.ydtask"
        )

        bad_path.write_text(
            "not a zip",
            encoding="utf-8",
        )

        inspection = (
            inspect_survey_task_package(
                bad_path
            )
        )

        self.assertFalse(
            inspection.valid
        )

        codes = {
            issue.code
            for issue in inspection.issues
        }

        self.assertIn(
            "PACKAGE_NOT_ZIP",
            codes,
        )


if __name__ == "__main__":
    unittest.main()
