import gc
import sqlite3
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
from services.survey_task_record_scope import (
    ensure_survey_task_record_scope_schema,
)


class SurveyTaskRecordScopeTestCase(
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
            / "scope.db"
        )

        initialize_application_database()

    def tearDown(self):
        gc.collect()
        database.DATA_DIR = (
            self.original_data_dir
        )
        database.DB_PATH = (
            self.original_db_path
        )
        self.temp_directory.cleanup()

    def _build_context(self):
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
                    "任务测试项目",
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
                    "任务测试批次",
                    "TASK-2026",
                ),
            )
            batch_id = int(
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
            office_id = int(
                office["id"]
            )

            scopes = connection.execute(
                """
                SELECT
                    cms.management_scope_uid,
                    cms.canal_unit_id,
                    cu.canal_unit_uid,
                    cu.name AS canal_name,
                    cu.canal_level,
                    cms.range_mode,
                    cms.start_stake_text,
                    cms.start_stake_value,
                    cms.end_stake_text,
                    cms.end_stake_value,
                    cms.sort_order,
                    cms.status,
                    cms.description
                FROM canal_management_scopes
                    AS cms
                JOIN canal_units AS cu
                  ON cu.id = cms.canal_unit_id
                WHERE cms.organization_unit_id = ?
                  AND cms.status = 'active'
                ORDER BY
                    cu.sort_order,
                    cms.sort_order,
                    cms.id
                """,
                (
                    office_id,
                ),
            ).fetchall()

            self.assertGreaterEqual(
                len(scopes),
                2,
            )

            form = connection.execute(
                """
                SELECT
                    fv.id AS form_version_id
                FROM form_versions AS fv
                JOIN form_definitions AS fd
                  ON fd.id
                    = fv.form_definition_id
                WHERE fd.series = 'series_2'
                  AND fd.record_type
                    = 'engineering'
                  AND fv.is_current = 1
                ORDER BY
                    fd.sort_order,
                    fv.id
                LIMIT 1
                """
            ).fetchone()

            workspace = connection.execute(
                """
                INSERT INTO survey_task_workspaces (
                    task_uid,
                    source_package_uid,
                    project_id,
                    survey_batch_id,
                    organization_unit_id,
                    task_name,
                    managed_package_relative_path,
                    source_package_sha256,
                    is_current
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, 1
                )
                """,
                (
                    "task-source-001",
                    "package-source-001",
                    project_id,
                    batch_id,
                    office_id,
                    "通远水管所任务",
                    (
                        "task_packages/"
                        "task-source-001/"
                        "package-source-001.ydtask"
                    ),
                    "0" * 64,
                ),
            )
            workspace_id = int(
                workspace.lastrowid
            )

            allowed = scopes[0]
            blocked = scopes[1]

            connection.execute(
                """
                INSERT INTO
                    survey_task_workspace_scopes (
                        task_workspace_id,
                        management_scope_uid,
                        canal_unit_id,
                        canal_unit_uid,
                        organization_unit_uid,
                        canal_name_snapshot,
                        canal_level_snapshot,
                        range_mode,
                        start_stake_text,
                        start_stake_value,
                        end_stake_text,
                        end_stake_value,
                        sort_order,
                        source_scope_status,
                        description
                    )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    workspace_id,
                    allowed[
                        "management_scope_uid"
                    ],
                    int(
                        allowed[
                            "canal_unit_id"
                        ]
                    ),
                    allowed[
                        "canal_unit_uid"
                    ],
                    office[
                        "organization_unit_uid"
                    ],
                    allowed[
                        "canal_name"
                    ],
                    allowed[
                        "canal_level"
                    ],
                    allowed[
                        "range_mode"
                    ],
                    allowed[
                        "start_stake_text"
                    ],
                    allowed[
                        "start_stake_value"
                    ],
                    allowed[
                        "end_stake_text"
                    ],
                    allowed[
                        "end_stake_value"
                    ],
                    int(
                        allowed[
                            "sort_order"
                        ]
                        or 0
                    ),
                    allowed["status"],
                    allowed[
                        "description"
                    ],
                ),
            )

        ensure_survey_task_record_scope_schema()

        return {
            "project_id": project_id,
            "batch_id": batch_id,
            "office_id": office_id,
            "allowed_canal_id": int(
                allowed[
                    "canal_unit_id"
                ]
            ),
            "blocked_canal_id": int(
                blocked[
                    "canal_unit_id"
                ]
            ),
            "form_version_id": int(
                form[
                    "form_version_id"
                ]
            ),
        }

    def _insert_record(
        self,
        context,
        canal_id,
        business_code,
    ):
        with database.get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO survey_records (
                    project_id,
                    survey_batch_id,
                    form_version_id,
                    record_type,
                    organization_unit_id,
                    canal_unit_id,
                    business_code,
                    record_status,
                    record_data_json
                )
                VALUES (
                    ?, ?, ?, 'engineering',
                    ?, ?, ?, 'draft', '{}'
                )
                """,
                (
                    context[
                        "project_id"
                    ],
                    context[
                        "batch_id"
                    ],
                    context[
                        "form_version_id"
                    ],
                    context[
                        "office_id"
                    ],
                    canal_id,
                    business_code,
                ),
            )
            return int(
                cursor.lastrowid
            )

    def test_allowed_record_is_stamped_with_task_uid(
        self,
    ):
        context = self._build_context()

        record_id = self._insert_record(
            context,
            context[
                "allowed_canal_id"
            ],
            "TASK-ALLOW-001",
        )

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT source_task_uid
                FROM survey_records
                WHERE id = ?
                """,
                (
                    record_id,
                ),
            ).fetchone()

        self.assertEqual(
            row["source_task_uid"],
            "task-source-001",
        )

    def test_out_of_scope_canal_is_blocked(
        self,
    ):
        context = self._build_context()

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "outside current task scope",
        ):
            self._insert_record(
                context,
                context[
                    "blocked_canal_id"
                ],
                "TASK-BLOCK-001",
            )

    def test_no_current_task_keeps_central_entry_compatible(
        self,
    ):
        context = self._build_context()

        with database.get_connection() as connection:
            connection.execute(
                """
                UPDATE survey_task_workspaces
                SET is_current = 0
                """
            )

        record_id = self._insert_record(
            context,
            context[
                "blocked_canal_id"
            ],
            "CENTRAL-001",
        )

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT source_task_uid
                FROM survey_records
                WHERE id = ?
                """,
                (
                    record_id,
                ),
            ).fetchone()

        self.assertIsNone(
            row["source_task_uid"]
        )


if __name__ == "__main__":
    unittest.main()
