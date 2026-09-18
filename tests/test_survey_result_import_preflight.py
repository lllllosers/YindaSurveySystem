import gc
import json
import sys
import tempfile
import unittest
from pathlib import Path


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
from services.survey_result_import_preflight import (
    preflight_survey_result_import,
)
from services.survey_result_package import (
    SurveyResultExportRequest,
    export_survey_result_package,
)
from services.survey_result_package_reader import (
    load_survey_result_package,
)


class SurveyResultImportPreflightTestCase(
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
            / "preflight.ydresult"
        )

        self._build_source_package()

    def tearDown(self):
        gc.collect()

        database.DATA_DIR = (
            self.original_data_dir
        )
        database.DB_PATH = (
            self.original_db_path
        )

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

    def _build_source_package(self):
        self._use_source()

        initialize_application_database()

        with database.get_connection() as connection:
            project = connection.execute(
                """
                INSERT INTO projects (
                    name,
                    short_name,
                    status
                )
                VALUES (?, ?, 'active')
                """,
                (
                    "2026成果预检项目",
                    "预检项目",
                ),
            )

            self.source_project_id = int(
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
                    self.source_project_id,
                    "2026成果预检批次",
                    "PREFLIGHT-2026",
                ),
            )

            self.source_batch_id = int(
                batch.lastrowid
            )

            project_row = connection.execute(
                """
                SELECT project_uid
                FROM projects
                WHERE id = ?
                """,
                (
                    self.source_project_id,
                ),
            ).fetchone()

            batch_row = connection.execute(
                """
                SELECT survey_batch_uid
                FROM survey_batches
                WHERE id = ?
                """,
                (
                    self.source_batch_id,
                ),
            ).fetchone()

            self.project_uid = (
                project_row[
                    "project_uid"
                ]
            )
            self.batch_uid = (
                batch_row[
                    "survey_batch_uid"
                ]
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

            self.office_id = int(
                office["id"]
            )
            self.canal_id = int(
                canal["id"]
            )
            self.form_version_id = int(
                form[
                    "form_version_id"
                ]
            )
            asset_type = str(
                form["asset_type"]
                or "test_asset"
            )

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
                    self.source_project_id,
                    "成果预检测试工程",
                    asset_type,
                    self.office_id,
                    self.canal_id,
                    "8-88-03-01-001",
                    self.source_batch_id,
                ),
            )

            self.source_asset_id = int(
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
                    survey_date,
                    overall_grade,
                    survey_comment,
                    record_status,
                    record_data_json
                )
                VALUES (
                    ?, ?, ?, 'engineering',
                    ?, ?, ?, ?, ?, ?, ?,
                    'completed', ?
                )
                """,
                (
                    self.source_project_id,
                    self.source_batch_id,
                    self.form_version_id,
                    self.office_id,
                    self.canal_id,
                    self.source_asset_id,
                    "8-88-03-01-001",
                    "2026-09-17",
                    "B",
                    "成果预检测试",
                    json.dumps(
                        {
                            "demo": "preflight",
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

            self.source_record_id = int(
                record.lastrowid
            )

            connection.execute(
                """
                INSERT INTO inspection_results (
                    survey_record_id,
                    item_code,
                    category,
                    item_name,
                    grade,
                    description,
                    remark
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.source_record_id,
                    "A01",
                    "主体",
                    "预检分项",
                    "B",
                    "描述",
                    "备注",
                ),
            )

        export_survey_result_package(
            SurveyResultExportRequest(
                project_id=(
                    self.source_project_id
                ),
                survey_batch_id=(
                    self.source_batch_id
                ),
                survey_record_ids=(
                    self.source_record_id,
                ),
                output_path=(
                    self.package_path
                ),
                result_name=(
                    "成果预检测试包"
                ),
            )
        )

    def _prepare_clean_target_context(
        self,
    ):
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
                    self.project_uid,
                    "2026成果预检项目",
                    "预检项目",
                ),
            )

            project_id = int(
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
                    self.batch_uid,
                    project_id,
                    "2026成果预检批次",
                    "PREFLIGHT-2026",
                ),
            )

            batch_id = int(
                batch.lastrowid
            )

        return (
            project_id,
            batch_id,
        )

    def test_clean_target_reports_new_data_without_writes(
        self,
    ):
        self._prepare_clean_target_context()

        with database.get_connection() as connection:
            before = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM engineering_assets)
                    AS assets,
                    (SELECT COUNT(*) FROM survey_records)
                    AS records,
                    (SELECT COUNT(*) FROM inspection_results)
                    AS inspections,
                    (SELECT COUNT(*) FROM survey_media)
                    AS media
                """
            ).fetchone()

        report = (
            preflight_survey_result_import(
                self.package_path
            )
        )

        self.assertTrue(
            report.can_import,
            report.format_text(),
        )
        self.assertEqual(
            report.new_assets,
            1,
        )
        self.assertEqual(
            report.new_records,
            1,
        )
        self.assertEqual(
            report.new_inspections,
            1,
        )

        with database.get_connection() as connection:
            after = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM engineering_assets)
                    AS assets,
                    (SELECT COUNT(*) FROM survey_records)
                    AS records,
                    (SELECT COUNT(*) FROM inspection_results)
                    AS inspections,
                    (SELECT COUNT(*) FROM survey_media)
                    AS media
                """
            ).fetchone()

        self.assertEqual(
            tuple(before),
            tuple(after),
        )

    def test_same_database_is_idempotent_candidate(
        self,
    ):
        self._use_source()

        report = (
            preflight_survey_result_import(
                self.package_path
            )
        )

        self.assertTrue(
            report.can_import,
            report.format_text(),
        )

        self.assertEqual(
            report.new_assets,
            0,
        )
        self.assertEqual(
            report.existing_assets,
            1,
        )
        self.assertEqual(
            report.new_records,
            0,
        )
        self.assertEqual(
            report.existing_records,
            1,
        )
        self.assertEqual(
            report.new_inspections,
            0,
        )
        self.assertEqual(
            report.existing_inspections,
            1,
        )

    def test_business_code_collision_is_reported_before_import(
        self,
    ):
        project_id, batch_id = (
            self._prepare_clean_target_context()
        )

        contents = (
            load_survey_result_package(
                self.package_path
            )
        )

        source_asset = (
            contents.engineering_assets[
                0
            ]
        )

        with database.get_connection() as connection:
            office = connection.execute(
                """
                SELECT id
                FROM organization_units
                WHERE organization_unit_uid = ?
                """,
                (
                    source_asset[
                        "organization_unit_uid"
                    ],
                ),
            ).fetchone()

            canal = connection.execute(
                """
                SELECT id
                FROM canal_units
                WHERE canal_unit_uid = ?
                """,
                (
                    source_asset[
                        "canal_unit_uid"
                    ],
                ),
            ).fetchone()

            connection.execute(
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
                    project_id,
                    "目标库已有另一工程",
                    source_asset[
                        "asset_type"
                    ],
                    int(
                        office["id"]
                    ),
                    int(
                        canal["id"]
                    ),
                    source_asset[
                        "business_code"
                    ],
                    batch_id,
                ),
            )

        report = (
            preflight_survey_result_import(
                self.package_path
            )
        )

        self.assertFalse(
            report.can_import
        )

        codes = {
            item.code
            for item in report.issues
        }

        self.assertIn(
            "ASSET_BUSINESS_CODE_COLLISION",
            codes,
        )


if __name__ == "__main__":
    unittest.main()
