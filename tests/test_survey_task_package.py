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


class SurveyTaskPackageTestCase(
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
            / "task_package.db"
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
                (
                    "ORG-D01-O03",
                ),
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

    def tearDown(self):
        gc.collect()

        database.DATA_DIR = (
            self.original_data_dir
        )
        database.DB_PATH = (
            self.original_db_path
        )

        self.temp_directory.cleanup()

    def _export(
        self,
        filename="通远水管所任务.ydtask",
        canal_ids=None,
    ):
        output_path = (
            self.temp_root
            / filename
        )

        result = (
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
                        tuple(
                            canal_ids
                            if canal_ids
                            is not None
                            else self.canal_ids
                        )
                    ),
                    task_name=(
                        "通远水管所调查任务"
                    ),
                    notes=(
                        "纸质外业调查任务范围"
                    ),
                    output_path=(
                        output_path
                    ),
                )
            )
        )

        return result

    def test_exports_expected_package_structure(
        self,
    ):
        result = self._export()

        self.assertTrue(
            result.output_path.exists()
        )

        self.assertEqual(
            result.output_path.suffix,
            ".ydtask",
        )

        with zipfile.ZipFile(
            result.output_path,
            "r",
        ) as archive:
            names = set(
                archive.namelist()
            )

        self.assertEqual(
            names,
            {
                "manifest.json",
                "task.json",
                (
                    "reference/"
                    "organization_units.json"
                ),
                (
                    "reference/"
                    "canal_units.json"
                ),
                (
                    "reference/"
                    "forms.json"
                ),
            },
        )

    def test_manifest_hashes_every_payload_file(
        self,
    ):
        result = self._export()

        with zipfile.ZipFile(
            result.output_path,
            "r",
        ) as archive:
            manifest = json.loads(
                archive.read(
                    "manifest.json"
                )
            )

            self.assertEqual(
                manifest[
                    "package_kind"
                ],
                "survey_task",
            )

            self.assertEqual(
                manifest[
                    "package_format_version"
                ],
                "1.0",
            )

            self.assertEqual(
                manifest[
                    "package_uid"
                ],
                result.package_uid,
            )

            for entry in manifest[
                "files"
            ]:
                content = archive.read(
                    entry["path"]
                )

                self.assertEqual(
                    len(content),
                    entry["size"],
                )

                self.assertEqual(
                    sha256(
                        content
                    ).hexdigest(),
                    entry["sha256"],
                )

    def test_task_uses_stable_uids_not_local_ids(
        self,
    ):
        result = self._export()

        with zipfile.ZipFile(
            result.output_path,
            "r",
        ) as archive:
            task = json.loads(
                archive.read(
                    "task.json"
                )
            )

            organizations = json.loads(
                archive.read(
                    (
                        "reference/"
                        "organization_units.json"
                    )
                )
            )

            canals = json.loads(
                archive.read(
                    (
                        "reference/"
                        "canal_units.json"
                    )
                )
            )

        self.assertIn(
            "project_uid",
            task["project"],
        )
        self.assertIn(
            "survey_batch_uid",
            task["survey_batch"],
        )

        self.assertNotIn(
            "project_id",
            task["project"],
        )
        self.assertNotIn(
            "survey_batch_id",
            task["survey_batch"],
        )

        for item in organizations[
            "items"
        ]:
            self.assertIn(
                "organization_uid",
                item,
            )
            self.assertNotIn(
                "id",
                item,
            )

        for item in canals[
            "items"
        ]:
            self.assertIn(
                "canal_uid",
                item,
            )
            self.assertNotIn(
                "id",
                item,
            )

    def test_reference_canals_include_selected_ancestors(
        self,
    ):
        result = self._export(
            canal_ids=(
                self.canal_ids[:1]
            )
        )

        with zipfile.ZipFile(
            result.output_path,
            "r",
        ) as archive:
            canals = json.loads(
                archive.read(
                    (
                        "reference/"
                        "canal_units.json"
                    )
                )
            )["items"]

        names = {
            item["name"]
            for item in canals
        }

        self.assertIn(
            "通远支渠",
            names,
        )
        self.assertIn(
            "总干渠",
            names,
        )

        self.assertEqual(
            result.selected_canal_count,
            1,
        )
        self.assertEqual(
            result.reference_canal_count,
            2,
        )

    def test_cannot_export_canal_owned_by_another_office(
        self,
    ):
        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM canal_units
                WHERE master_key = ?
                """,
                ("CANAL-S004",),
            ).fetchone()

        wrong_canal_id = int(
            row["id"]
        )

        with self.assertRaises(
            ValueError
        ) as context:
            self._export(
                canal_ids=(
                    wrong_canal_id,
                )
            )

        self.assertIn(
            "不属于当前管理单位",
            str(context.exception),
        )

    def test_existing_target_is_not_overwritten(
        self,
    ):
        result = self._export()

        before = (
            result.output_path
            .read_bytes()
        )

        with self.assertRaises(
            FileExistsError
        ):
            self._export()

        after = (
            result.output_path
            .read_bytes()
        )

        self.assertEqual(
            before,
            after,
        )

    def test_missing_extension_is_added(
        self,
    ):
        result = self._export(
            filename="任务包"
        )

        self.assertEqual(
            result.output_path.name,
            "任务包.ydtask",
        )


if __name__ == "__main__":
    unittest.main()
