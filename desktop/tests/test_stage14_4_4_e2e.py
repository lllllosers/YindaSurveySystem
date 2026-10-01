import gc
from hashlib import sha256
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
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
from services.canal_management_scope import (
    RANGE_MODE_SEGMENT_UNKNOWN,
    create_canal_management_scope,
)
from services.survey_result_import import (
    import_survey_result_package,
)
from services.survey_result_import_preflight import (
    SEVERITY_INFO,
    preflight_survey_result_import,
)
from services.survey_result_package import (
    SurveyResultExportRequest,
    export_survey_result_package,
)
from services.survey_task_package import (
    SurveyTaskExportRequest,
    export_survey_task_package,
)
from services.survey_task_workspace import (
    receive_survey_task_package,
)


class Stage1444EndToEndTestCase(
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

        self.parent_data_dir = (
            self.temp_root
            / "parent"
            / "local_data"
        )
        self.parent_db_path = (
            self.parent_data_dir
            / "parent.db"
        )

        self.child_data_dir = (
            self.temp_root
            / "child"
            / "local_data"
        )
        self.child_db_path = (
            self.child_data_dir
            / "child.db"
        )

        self.task_package_path = (
            self.temp_root
            / "dispatch.ydtask"
        )
        self.result_package_path = (
            self.temp_root
            / "return.ydresult"
        )

        self._build_parent_dispatch()
        self._build_child_result()
        self._change_parent_master_after_dispatch()

    def tearDown(self):
        gc.collect()

        database.DATA_DIR = (
            self.original_data_dir
        )
        database.DB_PATH = (
            self.original_db_path
        )

        self.temp_directory.cleanup()

    def _use_parent(self):
        database.DATA_DIR = (
            self.parent_data_dir
        )
        database.DB_PATH = (
            self.parent_db_path
        )

    def _use_child(self):
        database.DATA_DIR = (
            self.child_data_dir
        )
        database.DB_PATH = (
            self.child_db_path
        )

    def _build_parent_dispatch(self):
        self._use_parent()
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
                    "Stage14.4.4端到端项目",
                    "14.4.4E2E",
                ),
            )
            self.parent_project_id = int(
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
                    self.parent_project_id,
                    "Stage14.4.4端到端批次",
                    "E2E-1444",
                ),
            )
            self.parent_batch_id = int(
                batch.lastrowid
            )

            office = connection.execute(
                """
                SELECT
                    id,
                    organization_unit_uid
                FROM organization_units
                WHERE master_key = ?
                """,
                (
                    "ORG-D01-O03",
                ),
            ).fetchone()

            canal = connection.execute(
                """
                SELECT
                    id,
                    canal_unit_uid
                FROM canal_units
                WHERE master_key = ?
                """,
                (
                    "CANAL-G01",
                ),
            ).fetchone()

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
                    self.parent_project_id,
                    self.parent_batch_id,
                ),
            ).fetchone()

        self.office_id = int(
            office["id"]
        )
        self.office_uid = (
            office[
                "organization_unit_uid"
            ]
        )
        self.main_canal_id = int(
            canal["id"]
        )
        self.main_canal_uid = (
            canal[
                "canal_unit_uid"
            ]
        )
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

        first = (
            create_canal_management_scope(
                canal_unit_id=(
                    self.main_canal_id
                ),
                organization_unit_id=(
                    self.office_id
                ),
                range_mode=(
                    RANGE_MODE_SEGMENT_UNKNOWN
                ),
                sort_order=1,
                description=(
                    "总干渠第一冻结分管段"
                ),
            )
        )
        second = (
            create_canal_management_scope(
                canal_unit_id=(
                    self.main_canal_id
                ),
                organization_unit_id=(
                    self.office_id
                ),
                range_mode=(
                    RANGE_MODE_SEGMENT_UNKNOWN
                ),
                sort_order=2,
                description=(
                    "总干渠第二冻结分管段"
                ),
            )
        )

        self.scope_uids = (
            first[
                "management_scope_uid"
            ],
            second[
                "management_scope_uid"
            ],
        )
        self.selected_scope_uid = (
            self.scope_uids[
                1
            ]
        )

        task_result = (
            export_survey_task_package(
                SurveyTaskExportRequest(
                    project_id=(
                        self.parent_project_id
                    ),
                    survey_batch_id=(
                        self.parent_batch_id
                    ),
                    organization_unit_id=(
                        self.office_id
                    ),
                    management_scope_uids=(
                        self.scope_uids
                    ),
                    task_name=(
                        "总干渠同渠双分管段端到端任务"
                    ),
                    output_path=(
                        self.task_package_path
                    ),
                    notes=(
                        "Stage 14.4.4D"
                    ),
                )
            )
        )

        self.task_uid = (
            task_result.task_uid
        )

        with database.get_connection() as connection:
            issue = connection.execute(
                """
                SELECT
                    id,
                    task_uid,
                    selected_scope_count
                FROM survey_task_issues
                WHERE task_uid = ?
                """,
                (
                    self.task_uid,
                ),
            ).fetchone()

            issue_scopes = connection.execute(
                """
                SELECT
                    stis.management_scope_uid,
                    stis.canal_unit_uid
                FROM survey_task_issue_scopes AS stis
                JOIN survey_task_issues AS sti
                  ON sti.id = stis.task_issue_id
                WHERE sti.task_uid = ?
                ORDER BY stis.sort_order, stis.id
                """,
                (
                    self.task_uid,
                ),
            ).fetchall()

        self.assertIsNotNone(
            issue
        )
        self.assertEqual(
            int(
                issue[
                    "selected_scope_count"
                ]
            ),
            2,
        )
        self.assertEqual(
            {
                row[
                    "management_scope_uid"
                ]
                for row in issue_scopes
            },
            set(
                self.scope_uids
            ),
        )
        self.assertEqual(
            {
                row[
                    "canal_unit_uid"
                ]
                for row in issue_scopes
            },
            {
                self.main_canal_uid,
            },
        )

    def _build_child_result(self):
        self._use_child()
        initialize_application_database()

        receive_result = (
            receive_survey_task_package(
                self.task_package_path
            )
        )

        self.assertEqual(
            receive_result.task_uid,
            self.task_uid,
        )
        self.assertEqual(
            receive_result.selected_management_scope_count,
            2,
        )

        with database.get_connection() as connection:
            scopes = connection.execute(
                """
                SELECT
                    stws.management_scope_uid,
                    stws.canal_unit_id,
                    stws.canal_unit_uid
                FROM survey_task_workspace_scopes AS stws
                JOIN survey_task_workspaces AS stw
                  ON stw.id = stws.task_workspace_id
                WHERE stw.task_uid = ?
                ORDER BY stws.sort_order, stws.id
                """,
                (
                    self.task_uid,
                ),
            ).fetchall()

            selected = next(
                row
                for row in scopes
                if row[
                    "management_scope_uid"
                ]
                == self.selected_scope_uid
            )

            self.assertEqual(
                {
                    row[
                        "canal_unit_id"
                    ]
                    for row in scopes
                },
                {
                    int(
                        selected[
                            "canal_unit_id"
                        ]
                    ),
                },
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
                    receive_result.project_id,
                    "总干渠端到端测试工程",
                    form[
                        "asset_type"
                    ],
                    receive_result.organization_unit_id,
                    int(
                        selected[
                            "canal_unit_id"
                        ]
                    ),
                    "E2E-1444-001",
                    receive_result.survey_batch_id,
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
                    source_management_scope_uid,
                    business_code,
                    survey_date,
                    overall_grade,
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
                    receive_result.project_id,
                    receive_result.survey_batch_id,
                    int(
                        form[
                            "form_version_id"
                        ]
                    ),
                    receive_result.organization_unit_id,
                    int(
                        selected[
                            "canal_unit_id"
                        ]
                    ),
                    int(
                        asset.lastrowid
                    ),
                    self.selected_scope_uid,
                    "E2E-1444-001",
                    "2026-09-18",
                    "B",
                    json.dumps(
                        {
                            "stage": "14.4.4D",
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            self.child_record_id = int(
                record.lastrowid
            )

            provenance = connection.execute(
                """
                SELECT
                    survey_record_uid,
                    source_task_uid,
                    source_management_scope_uid
                FROM survey_records
                WHERE id = ?
                """,
                (
                    self.child_record_id,
                ),
            ).fetchone()

        self.record_uid = (
            provenance[
                "survey_record_uid"
            ]
        )

        self.assertEqual(
            provenance[
                "source_task_uid"
            ],
            self.task_uid,
        )
        self.assertEqual(
            provenance[
                "source_management_scope_uid"
            ],
            self.selected_scope_uid,
        )

        export_survey_result_package(
            SurveyResultExportRequest(
                project_id=(
                    receive_result.project_id
                ),
                survey_batch_id=(
                    receive_result.survey_batch_id
                ),
                survey_record_ids=(
                    self.child_record_id,
                ),
                output_path=(
                    self.result_package_path
                ),
                result_name=(
                    "Stage14.4.4端到端成果"
                ),
            )
        )

    def _change_parent_master_after_dispatch(
        self,
    ):
        self._use_parent()

        with database.get_connection() as connection:
            connection.execute(
                """
                UPDATE canal_management_scopes
                SET
                    status = 'inactive',
                    description = ?
                WHERE management_scope_uid = ?
                """,
                (
                    "任务下发后当前主数据发生变化",
                    self.selected_scope_uid,
                ),
            )

    def _fake_backup(self):
        path = (
            self.parent_data_dir
            / "backups"
            / "stage14_4_4d_fake.db"
        )
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.write_bytes(
            b"stage14.4.4d"
        )
        return path

    def _rewrite_result_provenance(
        self,
        *,
        task_uid=None,
        scope_uid=None,
        filename,
    ):
        with zipfile.ZipFile(
            self.result_package_path,
            "r",
        ) as archive:
            files = {
                info.filename: archive.read(
                    info.filename
                )
                for info in archive.infolist()
                if not info.is_dir()
            }

        records = json.loads(
            files[
                "data/survey_records.json"
            ].decode("utf-8")
        )

        item = records[
            "items"
        ][0]

        if task_uid is not None:
            item[
                "source_task_uid"
            ] = task_uid

        if scope_uid is not None:
            item[
                "source_management_scope_uid"
            ] = scope_uid

        record_payload = (
            json.dumps(
                records,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")

        files[
            "data/survey_records.json"
        ] = record_payload

        if task_uid is not None:
            result_document = json.loads(
                files[
                    "result.json"
                ].decode("utf-8")
            )
            result_document[
                "source_task_uid"
            ] = task_uid
            result_document[
                "source_task_uids"
            ] = [
                task_uid,
            ]

            result_payload = (
                json.dumps(
                    result_document,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            ).encode("utf-8")

            files[
                "result.json"
            ] = result_payload

        manifest = json.loads(
            files[
                "manifest.json"
            ].decode("utf-8")
        )

        if task_uid is not None:
            manifest[
                "source_task_uid"
            ] = task_uid
            manifest[
                "source_task_uids"
            ] = [
                task_uid,
            ]

        for entry in manifest[
            "files"
        ]:
            logical_path = entry[
                "path"
            ]

            if logical_path == (
                "data/survey_records.json"
            ):
                entry[
                    "size"
                ] = len(
                    files[
                        logical_path
                    ]
                )
                entry[
                    "sha256"
                ] = sha256(
                    files[
                        logical_path
                    ]
                ).hexdigest()

            elif (
                logical_path
                == "result.json"
                and task_uid
                is not None
            ):
                entry[
                    "size"
                ] = len(
                    files[
                        logical_path
                    ]
                )
                entry[
                    "sha256"
                ] = sha256(
                    files[
                        logical_path
                    ]
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
            / filename
        )

        with zipfile.ZipFile(
            rewritten,
            "w",
            compression=(
                zipfile.ZIP_DEFLATED
            ),
        ) as archive:
            for logical_path, content in (
                files.items()
            ):
                archive.writestr(
                    logical_path,
                    content,
                )

        return rewritten

    @patch(
        "services.survey_result_import."
        "create_database_backup"
    )
    def test_full_round_trip_uses_frozen_scope_authority(
        self,
        mock_backup,
    ):
        self._use_parent()

        report = (
            preflight_survey_result_import(
                self.result_package_path
            )
        )

        self.assertTrue(
            report.can_import,
            report.format_text(),
        )

        info_codes = {
            issue.code
            for issue in report.issues
            if issue.severity
            == SEVERITY_INFO
        }
        all_codes = {
            issue.code
            for issue in report.issues
        }

        self.assertIn(
            "SOURCE_SCOPE_CURRENT_MASTER_CHANGED",
            info_codes,
        )
        self.assertIn(
            "SOURCE_TASK_PROVENANCE_VERIFIED",
            all_codes,
        )

        mock_backup.return_value = (
            self._fake_backup()
        )

        result = (
            import_survey_result_package(
                self.result_package_path
            )
        )

        self.assertFalse(
            result.already_imported
        )
        self.assertEqual(
            result.imported_records,
            1,
        )

        with database.get_connection() as connection:
            imported = connection.execute(
                """
                SELECT
                    source_task_uid,
                    source_management_scope_uid,
                    canal_unit_id,
                    organization_unit_id
                FROM survey_records
                WHERE survey_record_uid = ?
                """,
                (
                    self.record_uid,
                ),
            ).fetchone()

            canal = connection.execute(
                """
                SELECT canal_unit_uid
                FROM canal_units
                WHERE id = ?
                """,
                (
                    imported[
                        "canal_unit_id"
                    ],
                ),
            ).fetchone()

            organization = connection.execute(
                """
                SELECT organization_unit_uid
                FROM organization_units
                WHERE id = ?
                """,
                (
                    imported[
                        "organization_unit_id"
                    ],
                ),
            ).fetchone()

        self.assertEqual(
            imported[
                "source_task_uid"
            ],
            self.task_uid,
        )
        self.assertEqual(
            imported[
                "source_management_scope_uid"
            ],
            self.selected_scope_uid,
        )
        self.assertEqual(
            canal[
                "canal_unit_uid"
            ],
            self.main_canal_uid,
        )
        self.assertEqual(
            organization[
                "organization_unit_uid"
            ],
            self.office_uid,
        )

    def test_wrong_scope_is_rejected_end_to_end(
        self,
    ):
        wrong_package = (
            self._rewrite_result_provenance(
                scope_uid=(
                    "scope-not-issued-e2e"
                ),
                filename=(
                    "wrong_scope.ydresult"
                ),
            )
        )

        self._use_parent()

        report = (
            preflight_survey_result_import(
                wrong_package
            )
        )

        self.assertFalse(
            report.can_import
        )

        codes = {
            issue.code
            for issue in report.issues
        }

        self.assertIn(
            "SOURCE_SCOPE_ISSUE_MISSING",
            codes,
        )

    def test_foreign_task_is_rejected_end_to_end(
        self,
    ):
        foreign_package = (
            self._rewrite_result_provenance(
                task_uid=(
                    "foreign-task-e2e"
                ),
                filename=(
                    "foreign_task.ydresult"
                ),
            )
        )

        self._use_parent()

        report = (
            preflight_survey_result_import(
                foreign_package
            )
        )

        self.assertFalse(
            report.can_import
        )

        codes = {
            issue.code
            for issue in report.issues
        }

        self.assertIn(
            "SOURCE_TASK_ISSUE_MISSING",
            codes,
        )


if __name__ == "__main__":
    unittest.main()
