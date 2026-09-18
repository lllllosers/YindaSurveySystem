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
                ("任务测试项目",),
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
                ("ORG-D01-O03",),
            ).fetchone()

            allowed = connection.execute(
                """
                SELECT
                    id,
                    canal_unit_uid,
                    name,
                    canal_level
                FROM canal_units
                WHERE master_key = ?
                """,
                ("CANAL-G01",),
            ).fetchone()

            blocked = connection.execute(
                """
                SELECT id
                FROM canal_units
                WHERE master_key = ?
                """,
                ("CANAL-S001",),
            ).fetchone()

            form = connection.execute(
                """
                SELECT fv.id AS form_version_id
                FROM form_versions AS fv
                JOIN form_definitions AS fd
                  ON fd.id = fv.form_definition_id
                WHERE fd.series = 'series_2'
                  AND fd.record_type = 'engineering'
                  AND fv.is_current = 1
                ORDER BY fd.sort_order, fv.id
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    "task-source-001",
                    "package-source-001",
                    project_id,
                    batch_id,
                    int(office["id"]),
                    "同渠双分管段任务",
                    (
                        "task_packages/task-source-001/"
                        "package-source-001.ydtask"
                    ),
                    "0" * 64,
                ),
            )
            workspace_id = int(
                workspace.lastrowid
            )

            for index, uid in enumerate(
                (
                    "task-scope-a",
                    "task-scope-b",
                ),
                start=1,
            ):
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
                        ?, ?, ?, ?, ?, ?, ?,
                        'segment_unknown',
                        NULL, NULL, NULL, NULL,
                        ?, 'active', ?
                    )
                    """,
                    (
                        workspace_id,
                        uid,
                        int(allowed["id"]),
                        allowed[
                            "canal_unit_uid"
                        ],
                        office[
                            "organization_unit_uid"
                        ],
                        allowed["name"],
                        allowed["canal_level"],
                        index,
                        f"分管段{index}",
                    ),
                )

        return {
            "project_id": project_id,
            "batch_id": batch_id,
            "office_id": int(
                office["id"]
            ),
            "allowed_canal_id": int(
                allowed["id"]
            ),
            "blocked_canal_id": int(
                blocked["id"]
            ),
            "scope_a": "task-scope-a",
            "scope_b": "task-scope-b",
            "form_version_id": int(
                form["form_version_id"]
            ),
        }

    def _insert_record(
        self,
        context,
        canal_id,
        business_code,
        *,
        scope_uid=None,
        source_task_uid=None,
        project_id=None,
        batch_id=None,
        office_id=None,
    ):
        target_project_id = (
            context["project_id"]
            if project_id is None
            else project_id
        )
        target_batch_id = (
            context["batch_id"]
            if batch_id is None
            else batch_id
        )
        target_office_id = (
            context["office_id"]
            if office_id is None
            else office_id
        )

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
                    source_task_uid,
                    source_management_scope_uid,
                    business_code,
                    record_status,
                    record_data_json
                )
                VALUES (
                    ?, ?, ?, 'engineering',
                    ?, ?, ?, ?, ?, 'draft', '{}'
                )
                """,
                (
                    target_project_id,
                    target_batch_id,
                    context["form_version_id"],
                    target_office_id,
                    canal_id,
                    source_task_uid,
                    scope_uid,
                    business_code,
                ),
            )
            return int(
                cursor.lastrowid
            )

    def test_explicit_scope_stamps_task_and_scope(
        self,
    ):
        context = self._build_context()

        record_id = self._insert_record(
            context,
            context["allowed_canal_id"],
            "TASK-ALLOW-001",
            scope_uid=context["scope_a"],
        )

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    source_task_uid,
                    source_management_scope_uid
                FROM survey_records
                WHERE id = ?
                """,
                (record_id,),
            ).fetchone()

        self.assertEqual(
            row["source_task_uid"],
            "task-source-001",
        )
        self.assertEqual(
            row[
                "source_management_scope_uid"
            ],
            context["scope_a"],
        )

    def test_same_canal_multiple_scopes_requires_explicit_scope(
        self,
    ):
        context = self._build_context()

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "required or ambiguous",
        ):
            self._insert_record(
                context,
                context["allowed_canal_id"],
                "TASK-AMBIGUOUS-001",
            )

    def test_scope_must_match_current_task_canal(
        self,
    ):
        context = self._build_context()

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "does not match current task canal",
        ):
            self._insert_record(
                context,
                context["blocked_canal_id"],
                "TASK-BLOCK-001",
                scope_uid=context["scope_a"],
            )

    def test_scope_uid_is_immutable(
        self,
    ):
        context = self._build_context()

        record_id = self._insert_record(
            context,
            context["allowed_canal_id"],
            "TASK-IMMUTABLE-001",
            scope_uid=context["scope_a"],
        )

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "source_management_scope_uid is immutable",
        ):
            with database.get_connection() as connection:
                connection.execute(
                    """
                    UPDATE survey_records
                    SET source_management_scope_uid = ?
                    WHERE id = ?
                    """,
                    (
                        context["scope_b"],
                        record_id,
                    ),
                )


    def test_single_scope_is_automatically_stamped(
        self,
    ):
        context = self._build_context()

        with database.get_connection() as connection:
            connection.execute(
                """
                DELETE FROM survey_task_workspace_scopes
                WHERE management_scope_uid = ?
                """,
                (
                    context["scope_b"],
                ),
            )

        record_id = self._insert_record(
            context,
            context["allowed_canal_id"],
            "TASK-AUTO-SCOPE-001",
        )

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    source_task_uid,
                    source_management_scope_uid
                FROM survey_records
                WHERE id = ?
                """,
                (record_id,),
            ).fetchone()

        self.assertEqual(
            row["source_task_uid"],
            "task-source-001",
        )
        self.assertEqual(
            row[
                "source_management_scope_uid"
            ],
            context["scope_a"],
        )

    def test_project_mismatch_is_rejected(
        self,
    ):
        context = self._build_context()

        with database.get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO projects (
                    name,
                    status
                )
                VALUES (?, 'inactive')
                """,
                ("其他项目",),
            )
            foreign_project_id = int(
                cursor.lastrowid
            )

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "outside current task context",
        ):
            self._insert_record(
                context,
                context["allowed_canal_id"],
                "TASK-WRONG-PROJECT-001",
                scope_uid=context["scope_a"],
                project_id=(
                    foreign_project_id
                ),
            )

    def test_batch_mismatch_is_rejected(
        self,
    ):
        context = self._build_context()

        with database.get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO survey_batches (
                    project_id,
                    batch_name,
                    batch_code,
                    status
                )
                VALUES (?, ?, ?, 'draft')
                """,
                (
                    context["project_id"],
                    "其他调查批次",
                    "TASK-OTHER-BATCH",
                ),
            )
            foreign_batch_id = int(
                cursor.lastrowid
            )

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "outside current task context",
        ):
            self._insert_record(
                context,
                context["allowed_canal_id"],
                "TASK-WRONG-BATCH-001",
                scope_uid=context["scope_a"],
                batch_id=(
                    foreign_batch_id
                ),
            )

    def test_organization_mismatch_is_rejected(
        self,
    ):
        context = self._build_context()

        with database.get_connection() as connection:
            foreign_office = connection.execute(
                """
                SELECT id
                FROM organization_units
                WHERE unit_type = 'water_office'
                  AND id != ?
                ORDER BY id
                LIMIT 1
                """,
                (context["office_id"],),
            ).fetchone()

        self.assertIsNotNone(
            foreign_office
        )

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "outside current task context",
        ):
            self._insert_record(
                context,
                context["allowed_canal_id"],
                "TASK-WRONG-OFFICE-001",
                scope_uid=context["scope_a"],
                office_id=int(
                    foreign_office["id"]
                ),
            )

    def test_source_task_uid_mismatch_is_rejected(
        self,
    ):
        context = self._build_context()

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "source task does not match current task",
        ):
            self._insert_record(
                context,
                context["allowed_canal_id"],
                "TASK-WRONG-SOURCE-001",
                scope_uid=context["scope_a"],
                source_task_uid=(
                    "foreign-task-uid"
                ),
            )

    def test_scope_from_foreign_workspace_is_rejected(
        self,
    ):
        context = self._build_context()

        with database.get_connection() as connection:
            office = connection.execute(
                """
                SELECT organization_unit_uid
                FROM organization_units
                WHERE id = ?
                """,
                (context["office_id"],),
            ).fetchone()

            canal = connection.execute(
                """
                SELECT
                    canal_unit_uid,
                    name,
                    canal_level
                FROM canal_units
                WHERE id = ?
                """,
                (
                    context[
                        "allowed_canal_id"
                    ],
                ),
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
                    ?, ?, ?, ?, ?, ?, ?, ?, 0
                )
                """,
                (
                    "foreign-task-001",
                    "foreign-package-001",
                    context["project_id"],
                    context["batch_id"],
                    context["office_id"],
                    "非当前任务",
                    (
                        "task_packages/"
                        "foreign-task-001/"
                        "foreign-package-001.ydtask"
                    ),
                    "f" * 64,
                ),
            )

            foreign_workspace_id = int(
                workspace.lastrowid
            )

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
                    ?, ?, ?, ?, ?, ?, ?,
                    'segment_unknown',
                    NULL, NULL, NULL, NULL,
                    1, 'active', ?
                )
                """,
                (
                    foreign_workspace_id,
                    "foreign-scope-only",
                    context[
                        "allowed_canal_id"
                    ],
                    canal[
                        "canal_unit_uid"
                    ],
                    office[
                        "organization_unit_uid"
                    ],
                    canal["name"],
                    canal["canal_level"],
                    "只属于非当前任务",
                ),
            )

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "does not match current task canal",
        ):
            self._insert_record(
                context,
                context[
                    "allowed_canal_id"
                ],
                "TASK-FOREIGN-SCOPE-001",
                scope_uid=(
                    "foreign-scope-only"
                ),
            )

    def test_source_task_uid_is_immutable(
        self,
    ):
        context = self._build_context()

        record_id = self._insert_record(
            context,
            context["allowed_canal_id"],
            "TASK-TASK-IMMUTABLE-001",
            scope_uid=context["scope_a"],
        )

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "source_task_uid is immutable",
        ):
            with database.get_connection() as connection:
                connection.execute(
                    """
                    UPDATE survey_records
                    SET source_task_uid = ?
                    WHERE id = ?
                    """,
                    (
                        "foreign-task-uid",
                        record_id,
                    ),
                )

    def test_task_sourced_record_cannot_leave_original_context(
        self,
    ):
        context = self._build_context()

        record_id = self._insert_record(
            context,
            context["allowed_canal_id"],
            "TASK-CONTEXT-IMMUTABLE-001",
            scope_uid=context["scope_a"],
        )

        with database.get_connection() as connection:
            foreign_office = connection.execute(
                """
                SELECT id
                FROM organization_units
                WHERE unit_type = 'water_office'
                  AND id != ?
                ORDER BY id
                LIMIT 1
                """,
                (context["office_id"],),
            ).fetchone()

        self.assertIsNotNone(
            foreign_office
        )

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "cannot leave assigned management scope",
        ):
            with database.get_connection() as connection:
                connection.execute(
                    """
                    UPDATE survey_records
                    SET organization_unit_id = ?
                    WHERE id = ?
                    """,
                    (
                        int(
                            foreign_office["id"]
                        ),
                        record_id,
                    ),
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
            context["blocked_canal_id"],
            "CENTRAL-001",
        )

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    source_task_uid,
                    source_management_scope_uid
                FROM survey_records
                WHERE id = ?
                """,
                (record_id,),
            ).fetchone()

        self.assertIsNone(
            row["source_task_uid"]
        )
        self.assertIsNone(
            row[
                "source_management_scope_uid"
            ]
        )


if __name__ == "__main__":
    unittest.main()
