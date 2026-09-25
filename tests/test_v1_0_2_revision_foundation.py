import gc
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
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
from services.survey_result_import import (
    import_survey_result_package,
)
from services.survey_result_package import (
    RESULT_SCHEMA_VERSION,
    SurveyResultExportRequest,
    export_survey_result_package,
)
from services.survey_result_package_reader import (
    load_survey_result_package,
)


class V102RevisionFoundationTestCase(
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

        self.source_data_dir = (
            self.temp_root
            / "source"
            / "local_data"
        )
        self.source_db_path = (
            self.source_data_dir
            / "source.db"
        )

        self.target_data_dir = (
            self.temp_root
            / "target"
            / "local_data"
        )
        self.target_db_path = (
            self.target_data_dir
            / "target.db"
        )

        self.package_path = (
            self.temp_root
            / "revision_foundation.ydresult"
        )

    def tearDown(self):
        database.DATA_DIR = (
            self.original_data_dir
        )
        database.DB_PATH = (
            self.original_db_path
        )
        gc.collect()
        self.temp_directory.cleanup()

    def _use_source(self):
        database.DATA_DIR = (
            self.source_data_dir
        )
        database.DB_PATH = (
            self.source_db_path
        )

    def _use_target(self):
        database.DATA_DIR = (
            self.target_data_dir
        )
        database.DB_PATH = (
            self.target_db_path
        )

    def _build_source(self):
        self._use_source()
        initialize_application_database()

        project = database.create_project(
            name="V1.0.2 revision source",
            short_name="revision-source",
        )
        project_id = int(
            project["project_id"]
        )

        batch = database.create_survey_batch(
            project_id=project_id,
            batch_name="V1.0.2 revision batch",
            batch_code="V102-REV",
        )
        batch_id = int(
            batch["batch_id"]
        )

        with database.get_connection() as connection:
            project_uid = connection.execute(
                """
                SELECT project_uid
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()[
                "project_uid"
            ]

            batch_uid = connection.execute(
                """
                SELECT survey_batch_uid
                FROM survey_batches
                WHERE id = ?
                """,
                (batch_id,),
            ).fetchone()[
                "survey_batch_uid"
            ]

            office = connection.execute(
                """
                SELECT id
                FROM organization_units
                WHERE unit_type = 'water_office'
                  AND status = 'active'
                ORDER BY id
                LIMIT 1
                """
            ).fetchone()

            canal = connection.execute(
                """
                SELECT id
                FROM canal_units
                WHERE status = 'active'
                ORDER BY id
                LIMIT 1
                """
            ).fetchone()

        self.assertIsNotNone(office)
        self.assertIsNotNone(canal)

        form = database.get_current_form_version(
            "form_2_2"
        )
        self.assertIsNotNone(form)

        created = database.create_engineering_survey(
            project_id=project_id,
            survey_batch_id=batch_id,
            form_version_id=int(
                form["id"]
            ),
            asset_name="revision test gate",
            asset_type=(
                form["asset_type"]
                or "sluice_gate"
            ),
            organization_unit_id=int(
                office["id"]
            ),
            canal_unit_id=int(
                canal["id"]
            ),
            business_code="1-01-03-02-001",
            record_data={
                "demo": "v1",
            },
            single_stake_text="CH0+100",
            single_stake_value=100.0,
            inspection_results=[],
            survey_date="2026-09-20",
            overall_grade="B",
            survey_comment="v1",
        )

        asset_id = int(
            created[
                "engineering_asset_id"
            ]
        )
        record_id = int(
            created[
                "survey_record_id"
            ]
        )

        with database.get_connection() as connection:
            asset_before = connection.execute(
                """
                SELECT
                    revision_no,
                    source_revision_no,
                    code_status
                FROM engineering_assets
                WHERE id = ?
                """,
                (asset_id,),
            ).fetchone()

            record_before = connection.execute(
                """
                SELECT
                    revision_no,
                    source_revision_no
                FROM survey_records
                WHERE id = ?
                """,
                (record_id,),
            ).fetchone()

        self.assertEqual(
            int(asset_before["revision_no"]),
            1,
        )
        self.assertEqual(
            int(asset_before["source_revision_no"]),
            0,
        )
        self.assertEqual(
            asset_before["code_status"],
            "provisional",
        )
        self.assertEqual(
            int(record_before["revision_no"]),
            1,
        )
        self.assertEqual(
            int(record_before["source_revision_no"]),
            0,
        )

        database.update_point_engineering_survey(
            survey_record_id=record_id,
            form_code="form_2_2",
            asset_name="revision test gate corrected",
            record_data={
                "demo": "v2",
            },
            single_stake_text="CH0+110",
            single_stake_value=110.0,
            inspection_results=[],
            survey_date="2026-09-20",
            overall_grade="C",
            survey_comment="corrected",
        )

        with database.get_connection() as connection:
            asset_after = connection.execute(
                """
                SELECT
                    revision_no,
                    source_revision_no
                FROM engineering_assets
                WHERE id = ?
                """,
                (asset_id,),
            ).fetchone()

            record_after = connection.execute(
                """
                SELECT
                    revision_no,
                    source_revision_no
                FROM survey_records
                WHERE id = ?
                """,
                (record_id,),
            ).fetchone()

            connection.execute(
                """
                UPDATE survey_records
                SET record_status = 'completed'
                WHERE id = ?
                """,
                (record_id,),
            )

        self.assertEqual(
            int(asset_after["revision_no"]),
            2,
        )
        self.assertEqual(
            int(asset_after["source_revision_no"]),
            0,
        )
        self.assertEqual(
            int(record_after["revision_no"]),
            2,
        )
        self.assertEqual(
            int(record_after["source_revision_no"]),
            0,
        )

        result = export_survey_result_package(
            SurveyResultExportRequest(
                project_id=project_id,
                survey_batch_id=batch_id,
                survey_record_ids=(
                    record_id,
                ),
                output_path=(
                    self.package_path
                ),
                result_name=(
                    "revision foundation"
                ),
            )
        )

        self.assertTrue(
            result.output_path.exists()
        )

        contents = (
            load_survey_result_package(
                self.package_path
            )
        )

        self.assertEqual(
            RESULT_SCHEMA_VERSION,
            "2.2",
        )
        self.assertEqual(
            contents.result[
                "result_schema_version"
            ],
            "2.2",
        )
        self.assertEqual(
            int(
                contents.engineering_assets[
                    0
                ][
                    "revision_no"
                ]
            ),
            2,
        )
        self.assertEqual(
            int(
                contents.survey_records[
                    0
                ][
                    "revision_no"
                ]
            ),
            2,
        )

        return {
            "project_uid": project_uid,
            "batch_uid": batch_uid,
        }

    def test_revision_schema_and_package_contract(
        self,
    ):
        self._build_source()

    def test_import_preserves_incoming_revision_as_source_baseline(
        self,
    ):
        source = self._build_source()

        self._use_target()
        initialize_application_database()

        with database.get_connection() as connection:
            project = connection.execute(
                """
                INSERT INTO projects (
                    project_uid,
                    name,
                    short_name,
                    status
                )
                VALUES (?, ?, ?, 'active')
                """,
                (
                    source["project_uid"],
                    "V1.0.2 revision target",
                    "revision-target",
                ),
            )
            target_project_id = int(
                project.lastrowid
            )

            batch = connection.execute(
                """
                INSERT INTO survey_batches (
                    survey_batch_uid,
                    project_id,
                    batch_name,
                    batch_code,
                    status
                )
                VALUES (?, ?, ?, ?, 'active')
                """,
                (
                    source["batch_uid"],
                    target_project_id,
                    "V1.0.2 revision batch",
                    "V102-REV",
                ),
            )
            target_batch_id = int(
                batch.lastrowid
            )

        result = import_survey_result_package(
            self.package_path
        )

        self.assertEqual(
            result.imported_assets,
            1,
        )
        self.assertEqual(
            result.imported_records,
            1,
        )

        with database.get_connection() as connection:
            asset = connection.execute(
                """
                SELECT
                    revision_no,
                    source_revision_no
                FROM engineering_assets
                WHERE project_id = ?
                """,
                (
                    target_project_id,
                ),
            ).fetchone()

            record = connection.execute(
                """
                SELECT
                    revision_no,
                    source_revision_no
                FROM survey_records
                WHERE survey_batch_id = ?
                """,
                (
                    target_batch_id,
                ),
            ).fetchone()

        self.assertEqual(
            (
                int(asset["revision_no"]),
                int(
                    asset[
                        "source_revision_no"
                    ]
                ),
            ),
            (
                2,
                2,
            ),
        )
        self.assertEqual(
            (
                int(record["revision_no"]),
                int(
                    record[
                        "source_revision_no"
                    ]
                ),
            ),
            (
                2,
                2,
            ),
        )


if __name__ == "__main__":
    unittest.main()
