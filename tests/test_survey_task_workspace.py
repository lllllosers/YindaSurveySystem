import gc
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
from services.survey_task_package import (
    SurveyTaskExportRequest,
    export_survey_task_package,
)
from services.survey_task_workspace import (
    get_current_task_workspace,
    receive_survey_task_package,
)


class SurveyTaskWorkspaceTestCase(
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
            / "通远水管所任务.ydtask"
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

    def _build_source_task(self):
        self._use_source()

        initialize_application_database()

        with database.get_connection() as connection:
            project_cursor = (
                connection.execute(
                    """
                    INSERT INTO projects (
                        name,
                        short_name,
                        status
                    )
                    VALUES (?, ?, 'active')
                    """,
                    (
                        "2026年调查项目",
                        "2026调查",
                    ),
                )
            )

            project_id = int(
                project_cursor.lastrowid
            )

            batch_cursor = (
                connection.execute(
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
                        "2026年调查批次",
                        "2026",
                    ),
                )
            )

            batch_id = int(
                batch_cursor.lastrowid
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

            scope = connection.execute(
                """
                SELECT management_scope_uid
                FROM canal_management_scopes
                WHERE master_key = ?
                """,
                (
                    "CMS-CANAL-S001-ORG-D01-O03",
                ),
            ).fetchone()

            source_identity = (
                connection.execute(
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
            )

        export_result = (
            export_survey_task_package(
                SurveyTaskExportRequest(
                    project_id=(
                        project_id
                    ),
                    survey_batch_id=(
                        batch_id
                    ),
                    organization_unit_id=(
                        int(
                            office["id"]
                        )
                    ),
                    management_scope_uids=(
                        scope[
                            "management_scope_uid"
                        ],
                    ),
                    task_name=(
                        "通远水管所调查任务"
                    ),
                    output_path=(
                        self.package_path
                    ),
                    notes="Stage 12.1",
                )
            )
        )

        return {
            "export_result": (
                export_result
            ),
            "project_uid": (
                source_identity[
                    "project_uid"
                ]
            ),
            "batch_uid": (
                source_identity[
                    "survey_batch_uid"
                ]
            ),
        }

    def test_receive_task_creates_local_workspace_and_context(
        self,
    ):
        source = (
            self._build_source_task()
        )

        self._use_target()

        initialize_application_database()

        result = (
            receive_survey_task_package(
                self.package_path
            )
        )

        self.assertFalse(
            result.already_received
        )
        self.assertTrue(
            result.created_project
        )
        self.assertTrue(
            result.created_batch
        )
        self.assertEqual(
            result.selected_management_scope_count,
            1,
        )
        self.assertTrue(
            result.managed_package_path.exists()
        )

        with database.get_connection() as connection:
            project = connection.execute(
                """
                SELECT
                    project_uid,
                    status
                FROM projects
                WHERE id = ?
                """,
                (
                    result.project_id,
                ),
            ).fetchone()

            batch = connection.execute(
                """
                SELECT
                    survey_batch_uid,
                    status
                FROM survey_batches
                WHERE id = ?
                """,
                (
                    result.survey_batch_id,
                ),
            ).fetchone()

        self.assertEqual(
            project["project_uid"],
            source["project_uid"],
        )
        self.assertEqual(
            project["status"],
            "active",
        )
        self.assertEqual(
            batch[
                "survey_batch_uid"
            ],
            source["batch_uid"],
        )
        self.assertEqual(
            batch["status"],
            "active",
        )

        current = (
            get_current_task_workspace()
        )

        self.assertIsNotNone(
            current
        )
        self.assertEqual(
            current["task_uid"],
            (
                source[
                    "export_result"
                ].task_uid
            ),
        )
        self.assertEqual(
            len(
                current["canals"]
            ),
            1,
        )

    def test_same_task_receive_is_idempotent(
        self,
    ):
        self._build_source_task()

        self._use_target()

        initialize_application_database()

        first = (
            receive_survey_task_package(
                self.package_path
            )
        )

        second = (
            receive_survey_task_package(
                self.package_path
            )
        )

        self.assertFalse(
            first.already_received
        )
        self.assertTrue(
            second.already_received
        )
        self.assertEqual(
            first.task_workspace_id,
            second.task_workspace_id,
        )

        with database.get_connection() as connection:
            count = connection.execute(
                """
                SELECT COUNT(*) AS value
                FROM survey_task_workspaces
                """
            ).fetchone()

        self.assertEqual(
            int(
                count["value"]
            ),
            1,
        )

    def test_managed_master_identity_matches_across_computers(
        self,
    ):
        self._build_source_task()

        self._use_target()

        initialize_application_database()

        result = (
            receive_survey_task_package(
                self.package_path
            )
        )

        with database.get_connection() as connection:
            office = connection.execute(
                """
                SELECT
                    organization_unit_uid
                FROM organization_units
                WHERE id = ?
                """,
                (
                    result[
                        "organization_unit_id"
                    ]
                    if isinstance(
                        result,
                        dict,
                    )
                    else result.organization_unit_id,
                ),
            ).fetchone()

            expected = connection.execute(
                """
                SELECT
                    organization_unit_uid
                FROM organization_units
                WHERE master_key = ?
                """,
                (
                    "ORG-D01-O03",
                ),
            ).fetchone()

        self.assertEqual(
            office[
                "organization_unit_uid"
            ],
            expected[
                "organization_unit_uid"
            ],
        )


if __name__ == "__main__":
    unittest.main()
