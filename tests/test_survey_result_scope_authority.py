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
from services.survey_result_import_preflight import (
    SEVERITY_WARNING,
    preflight_survey_result_import,
)
from services.survey_result_package import (
    SurveyResultExportRequest,
    export_survey_result_package,
)
from services.survey_task_issue_history import (
    record_issued_survey_task,
)


class SurveyResultScopeAuthorityTestCase(
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
            / "scope_authority.ydresult"
        )

        self.task_uid = (
            "issued-task-authority-001"
        )

        self._build_source_package()
        self._prepare_target()

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
                    "成果来源校验项目",
                    "来源校验",
                ),
            )
            project_id = int(
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
                    project_id,
                    "2026来源校验批次",
                    "AUTH-2026",
                ),
            )
            batch_id = int(
                batch.lastrowid
            )

            identities = connection.execute(
                """
                SELECT
                    p.project_uid,
                    sb.survey_batch_uid
                FROM projects AS p
                JOIN survey_batches AS sb
                  ON sb.project_id = p.id
                WHERE p.id = ?
                  AND sb.id = ?
                """,
                (
                    project_id,
                    batch_id,
                ),
            ).fetchone()

            self.project_uid = (
                identities[
                    "project_uid"
                ]
            )
            self.batch_uid = (
                identities[
                    "survey_batch_uid"
                ]
            )

            scope = connection.execute(
                """
                SELECT
                    cms.management_scope_uid,
                    cms.canal_unit_id,
                    cms.organization_unit_id
                FROM canal_management_scopes AS cms
                WHERE cms.master_key = ?
                """,
                (
                    "CMS-CANAL-S001-ORG-D01-O03",
                ),
            ).fetchone()

            self.scope_uid = (
                scope[
                    "management_scope_uid"
                ]
            )
            office_id = int(
                scope[
                    "organization_unit_id"
                ]
            )
            canal_id = int(
                scope[
                    "canal_unit_id"
                ]
            )

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
                  AND fv.is_current = 1
                ORDER BY fd.sort_order, fv.id
                LIMIT 1
                """
            ).fetchone()

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
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, 'active'
                )
                """,
                (
                    project_id,
                    "来源校验测试工程",
                    form[
                        "asset_type"
                    ],
                    office_id,
                    canal_id,
                    "6-66-03-01-001",
                    batch_id,
                ),
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
                    project_id,
                    batch_id,
                    int(
                        form[
                            "form_version_id"
                        ]
                    ),
                    office_id,
                    canal_id,
                    int(
                        asset.lastrowid
                    ),
                    "6-66-03-01-001",
                ),
            )

            connection.execute(
                """
                UPDATE survey_records
                SET
                    source_task_uid = ?,
                    source_management_scope_uid = ?
                WHERE id = ?
                """,
                (
                    self.task_uid,
                    self.scope_uid,
                    int(
                        record.lastrowid
                    ),
                ),
            )

            record_id = int(
                record.lastrowid
            )

        export_survey_result_package(
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
                    "来源校验测试成果"
                ),
            )
        )

    def _prepare_target(self):
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
                    "成果来源校验项目",
                    "来源校验",
                ),
            )

            connection.execute(
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
                    int(
                        project.lastrowid
                    ),
                    "2026来源校验批次",
                    "AUTH-2026",
                ),
            )

    def _seed_matching_issue_history(
        self,
    ):
        self._use_target()

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    cms.management_scope_uid,
                    cu.canal_unit_uid,
                    cu.name AS canal_name,
                    cu.canal_level,
                    ou.organization_unit_uid,
                    ou.name AS organization_name,
                    dept.organization_unit_uid
                        AS department_uid,
                    dept.name AS department_name,
                    cms.range_mode,
                    cms.start_stake_text,
                    cms.start_stake_value,
                    cms.end_stake_text,
                    cms.end_stake_value,
                    cms.sort_order,
                    cms.status,
                    cms.description
                FROM canal_management_scopes AS cms
                JOIN canal_units AS cu
                  ON cu.id = cms.canal_unit_id
                JOIN organization_units AS ou
                  ON ou.id = cms.organization_unit_id
                JOIN organization_units AS dept
                  ON dept.id = ou.parent_id
                WHERE cms.management_scope_uid = ?
                """,
                (
                    self.scope_uid,
                ),
            ).fetchone()

        self.assertIsNotNone(
            row
        )

        manifest = {
            "task_uid": self.task_uid,
            "task_schema_version": "2.0",
            "app_version": "0.7.0",
            "project_uid": self.project_uid,
            "survey_batch_uid": self.batch_uid,
        }

        task_document = {
            "task_schema_version": "2.0",
            "task_uid": self.task_uid,
            "task_name": "来源校验下发任务",
            "notes": None,
            "project": {
                "project_uid": self.project_uid,
                "name": "成果来源校验项目",
                "short_name": "来源校验",
            },
            "survey_batch": {
                "survey_batch_uid": self.batch_uid,
                "batch_name": "2026来源校验批次",
                "batch_code": "AUTH-2026",
                "start_date": None,
                "end_date": None,
            },
            "assignment": {
                "department_uid": row[
                    "department_uid"
                ],
                "department_name": row[
                    "department_name"
                ],
                "organization_unit_uid": row[
                    "organization_unit_uid"
                ],
                "organization_name": row[
                    "organization_name"
                ],
            },
            "scope": {
                "selected_management_scope_uids": [
                    self.scope_uid,
                ],
                "selected_management_scope_count": 1,
            },
            "created_at": (
                "2026-09-18T18:00:00+08:00"
            ),
        }

        record_issued_survey_task(
            package_uid=(
                "authority-package-001"
            ),
            manifest=manifest,
            task_document=(
                task_document
            ),
            management_scopes=[
                {
                    "management_scope_uid": (
                        self.scope_uid
                    ),
                    "canal_uid": row[
                        "canal_unit_uid"
                    ],
                    "organization_unit_uid": (
                        row[
                            "organization_unit_uid"
                        ]
                    ),
                    "range_mode": row[
                        "range_mode"
                    ],
                    "start_stake_text": row[
                        "start_stake_text"
                    ],
                    "start_stake_value": row[
                        "start_stake_value"
                    ],
                    "end_stake_text": row[
                        "end_stake_text"
                    ],
                    "end_stake_value": row[
                        "end_stake_value"
                    ],
                    "sort_order": int(
                        row[
                            "sort_order"
                        ]
                        or 0
                    ),
                    "status": row[
                        "status"
                    ],
                    "description": row[
                        "description"
                    ],
                }
            ],
            canal_units=[
                {
                    "canal_uid": row[
                        "canal_unit_uid"
                    ],
                    "name": row[
                        "canal_name"
                    ],
                    "canal_level": row[
                        "canal_level"
                    ],
                }
            ],
        )

    def _rewrite_record_scope(
        self,
        scope_uid,
    ):
        with zipfile.ZipFile(
            self.package_path,
            "r",
        ) as archive:
            files = {
                info.filename: archive.read(
                    info.filename
                )
                for info in archive.infolist()
                if not info.is_dir()
            }

        document = json.loads(
            files[
                "data/survey_records.json"
            ].decode("utf-8")
        )

        document[
            "items"
        ][0][
            "source_management_scope_uid"
        ] = scope_uid

        payload = (
            json.dumps(
                document,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")

        files[
            "data/survey_records.json"
        ] = payload

        manifest = json.loads(
            files[
                "manifest.json"
            ].decode("utf-8")
        )

        for entry in manifest[
            "files"
        ]:
            if (
                entry[
                    "path"
                ]
                == "data/survey_records.json"
            ):
                entry[
                    "size"
                ] = len(
                    payload
                )
                entry[
                    "sha256"
                ] = sha256(
                    payload
                ).hexdigest()

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

        rewritten = (
            self.temp_root
            / "wrong_scope.ydresult"
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

    def test_matching_issued_snapshot_allows_import(
        self,
    ):
        self._seed_matching_issue_history()

        report = (
            preflight_survey_result_import(
                self.package_path
            )
        )

        self.assertTrue(
            report.can_import,
            report.format_text(),
        )

        codes = {
            item.code
            for item in report.issues
        }

        self.assertIn(
            "SOURCE_TASK_PROVENANCE_VERIFIED",
            codes,
        )

    def test_missing_issued_task_is_error(
        self,
    ):
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
            "SOURCE_TASK_ISSUE_MISSING",
            codes,
        )

    def test_scope_not_in_issued_task_is_error(
        self,
    ):
        self._seed_matching_issue_history()

        wrong_package = (
            self._rewrite_record_scope(
                "scope-not-issued"
            )
        )

        report = (
            preflight_survey_result_import(
                wrong_package
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
            "SOURCE_SCOPE_ISSUE_MISSING",
            codes,
        )

    def test_current_scope_change_is_warning_only(
        self,
    ):
        self._seed_matching_issue_history()

        self._use_target()

        with database.get_connection() as connection:
            connection.execute(
                """
                UPDATE canal_management_scopes
                SET status = 'inactive'
                WHERE management_scope_uid = ?
                """,
                (
                    self.scope_uid,
                ),
            )

        report = (
            preflight_survey_result_import(
                self.package_path
            )
        )

        self.assertTrue(
            report.can_import,
            report.format_text(),
        )

        warning_codes = {
            item.code
            for item in report.issues
            if item.severity
            == SEVERITY_WARNING
        }

        self.assertIn(
            "SOURCE_SCOPE_CURRENT_MASTER_CHANGED",
            warning_codes,
        )


if __name__ == "__main__":
    unittest.main()
