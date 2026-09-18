import gc
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
from services.survey_result_package import (
    SurveyResultExportRequest,
    export_survey_result_package,
)
from services.survey_result_package_reader import (
    inspect_survey_result_package,
)


class SurveyResultTaskSourcesTestCase(
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
            / "task_sources.db"
        )

        initialize_application_database()

        with database.get_connection() as connection:
            project = connection.execute(
                """
                INSERT INTO projects (
                    name,
                    status
                )
                VALUES (?, 'active')
                """,
                (
                    "多来源成果测试",
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
                VALUES (?, ?, ?, 'active')
                """,
                (
                    self.project_id,
                    "2026批次",
                    "2026-MULTI",
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

            canal = connection.execute(
                """
                SELECT id
                FROM canal_units
                WHERE master_key = ?
                """,
                (
                    "CANAL-S001",
                ),
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

            office_id = int(
                office["id"]
            )
            canal_id = int(
                canal["id"]
            )
            form_version_id = int(
                form[
                    "form_version_id"
                ]
            )
            asset_type = str(
                form["asset_type"]
                or "test_asset"
            )

            self.record_ids = []

            for index, task_uid in enumerate(
                (
                    "task-alpha",
                    "task-beta",
                ),
                start=1,
            ):
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
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
                    """,
                    (
                        self.project_id,
                        f"测试工程{index}",
                        asset_type,
                        office_id,
                        canal_id,
                        f"9-99-03-01-{index:03d}",
                        self.batch_id,
                    ),
                )

                asset_id = int(
                    asset.lastrowid
                )

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
                        record_status,
                        record_data_json
                    )
                    VALUES (
                        ?, ?, ?, 'engineering',
                        ?, ?, ?, ?, 'completed', '{}'
                    )
                    """,
                    (
                        self.project_id,
                        self.batch_id,
                        form_version_id,
                        office_id,
                        canal_id,
                        asset_id,
                        f"9-99-03-01-{index:03d}",
                    ),
                )

                record_id = int(
                    record.lastrowid
                )

                connection.execute(
                    """
                    UPDATE survey_records
                    SET source_task_uid = ?
                    WHERE id = ?
                    """,
                    (
                        task_uid,
                        record_id,
                    ),
                )

                self.record_ids.append(
                    record_id
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

    def test_multi_source_is_derived_from_records(
        self,
    ):
        output_path = (
            self.temp_root
            / "multi.ydresult"
        )

        export_survey_result_package(
            SurveyResultExportRequest(
                project_id=(
                    self.project_id
                ),
                survey_batch_id=(
                    self.batch_id
                ),
                survey_record_ids=tuple(
                    self.record_ids
                ),
                output_path=(
                    output_path
                ),
                result_name=(
                    "多来源调查成果"
                ),
            )
        )

        with zipfile.ZipFile(
            output_path,
            "r",
        ) as archive:
            manifest = json.loads(
                archive.read(
                    "manifest.json"
                )
            )
            result = json.loads(
                archive.read(
                    "result.json"
                )
            )
            records = json.loads(
                archive.read(
                    (
                        "data/"
                        "survey_records.json"
                    )
                )
            )["items"]

        expected = [
            "task-alpha",
            "task-beta",
        ]

        self.assertEqual(
            result[
                "source_task_uids"
            ],
            expected,
        )
        self.assertIsNone(
            result[
                "source_task_uid"
            ]
        )

        self.assertEqual(
            manifest[
                "source_task_uids"
            ],
            expected,
        )
        self.assertIsNone(
            manifest[
                "source_task_uid"
            ]
        )

        self.assertEqual(
            {
                item[
                    "source_task_uid"
                ]
                for item in records
            },
            set(expected),
        )

        inspection = (
            inspect_survey_result_package(
                output_path
            )
        )

        self.assertTrue(
            inspection.valid,
            inspection.format_text(),
        )


if __name__ == "__main__":
    unittest.main()
