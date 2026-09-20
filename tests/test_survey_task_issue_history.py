import gc
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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
from services.survey_task_issue_history import (
    get_issued_survey_task,
    get_issued_task_scope_snapshot,
)
from services.survey_task_package import (
    SurveyTaskExportRequest,
    export_survey_task_package,
)


class SurveyTaskIssueHistoryTestCase(
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
            / "issue_history.db"
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
                VALUES (?, ?, 'active')
                """,
                (
                    "任务下发历史测试项目",
                    "下发测试",
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
                    "2026年任务批次",
                    "ISSUE-2026",
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
                office[
                    "id"
                ]
            )

            scopes = connection.execute(
                """
                SELECT
                    management_scope_uid
                FROM canal_management_scopes
                WHERE master_key IN (
                    'CMS-CANAL-S001-ORG-D01-O03',
                    'CMS-CANAL-S002-ORG-D01-O03'
                )
                ORDER BY sort_order, id
                """
            ).fetchall()

            self.scope_uids = tuple(
                row[
                    "management_scope_uid"
                ]
                for row in scopes
            )

        self.assertEqual(
            len(
                self.scope_uids
            ),
            2,
        )

        self.package_path = (
            self.temp_root
            / "authority.ydtask"
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
        *,
        output_path=None,
        scope_uids=None,
    ):
        return export_survey_task_package(
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
                management_scope_uids=(
                    tuple(
                        self.scope_uids
                        if scope_uids is None
                        else scope_uids
                    )
                ),
                task_name=(
                    "通远水管所任务"
                ),
                notes=(
                    "冻结下发事实"
                ),
                output_path=(
                    output_path
                    or self.package_path
                ),
            )
        )

    def test_export_persists_authoritative_issue_snapshot(
        self,
    ):
        result = self._export()

        issue = get_issued_survey_task(
            result.task_uid
        )

        self.assertIsNotNone(
            issue
        )
        self.assertEqual(
            issue[
                "task_uid"
            ],
            result.task_uid,
        )
        self.assertEqual(
            issue[
                "source_package_uid"
            ],
            result.package_uid,
        )
        self.assertIsNone(
            issue[
                "parent_task_uid"
            ]
        )
        self.assertEqual(
            issue[
                "root_task_uid"
            ],
            result.task_uid,
        )
        self.assertEqual(
            issue[
                "task_depth"
            ],
            0,
        )
        self.assertEqual(
            issue[
                "selected_scope_count"
            ],
            2,
        )
        self.assertEqual(
            {
                item[
                    "management_scope_uid"
                ]
                for item in issue[
                    "management_scopes"
                ]
            },
            set(
                self.scope_uids
            ),
        )

        self.assertTrue(
            all(
                item[
                    "organization_unit_uid"
                ]
                == issue[
                    "organization_unit_uid"
                ]
                for item in issue[
                    "management_scopes"
                ]
            )
        )

    def test_issue_snapshot_is_independent_from_live_scope_changes(
        self,
    ):
        result = self._export(
            scope_uids=(
                self.scope_uids[
                    0
                ],
            )
        )

        before = (
            get_issued_task_scope_snapshot(
                result.task_uid,
                self.scope_uids[
                    0
                ],
            )
        )

        self.assertIsNotNone(
            before
        )

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
                    "当前主数据后来已修改",
                    self.scope_uids[
                        0
                    ],
                ),
            )

        after = (
            get_issued_task_scope_snapshot(
                result.task_uid,
                self.scope_uids[
                    0
                ],
            )
        )

        self.assertEqual(
            after[
                "source_scope_status"
            ],
            "active",
        )
        self.assertNotEqual(
            after[
                "description"
            ],
            "当前主数据后来已修改",
        )
        self.assertEqual(
            after,
            before,
        )

    def test_issue_history_is_immutable(
        self,
    ):
        result = self._export(
            scope_uids=(
                self.scope_uids[
                    0
                ],
            )
        )

        issue = get_issued_survey_task(
            result.task_uid
        )

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "issued survey task history is immutable",
        ):
            with database.get_connection() as connection:
                connection.execute(
                    """
                    UPDATE survey_task_issues
                    SET task_name = ?
                    WHERE task_uid = ?
                    """,
                    (
                        "被错误修改",
                        result.task_uid,
                    ),
                )

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "issued survey task scope history is immutable",
        ):
            with database.get_connection() as connection:
                connection.execute(
                    """
                    UPDATE survey_task_issue_scopes
                    SET description = ?
                    WHERE task_issue_id = ?
                    """,
                    (
                        "被错误修改",
                        issue[
                            "id"
                        ],
                    ),
                )

    @patch(
        "services.survey_task_package."
        "record_issued_survey_task",
        side_effect=RuntimeError(
            "模拟下发历史保存失败"
        ),
    )
    def test_unregistered_package_is_removed_if_history_save_fails(
        self,
        mock_record,
    ):
        output_path = (
            self.temp_root
            / "must_not_escape.ydtask"
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "模拟下发历史保存失败",
        ):
            self._export(
                output_path=(
                    output_path
                ),
                scope_uids=(
                    self.scope_uids[
                        0
                    ],
                ),
            )

        self.assertTrue(
            mock_record.called
        )
        self.assertFalse(
            output_path.exists()
        )

        with database.get_connection() as connection:
            count = connection.execute(
                """
                SELECT COUNT(*) AS value
                FROM survey_task_issues
                """
            ).fetchone()

        self.assertEqual(
            int(
                count[
                    "value"
                ]
            ),
            0,
        )

    def test_bootstrap_creates_issue_authority_schema_idempotently(
        self,
    ):
        first = initialize_application_database()
        second = initialize_application_database()

        self.assertTrue(
            first[
                "survey_task_issue_history"
            ][
                "ready"
            ]
        )
        self.assertTrue(
            second[
                "survey_task_issue_history"
            ][
                "ready"
            ]
        )

        with database.get_connection() as connection:
            tables = {
                row[
                    "name"
                ]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                ).fetchall()
            }

        self.assertIn(
            "survey_task_issues",
            tables,
        )
        self.assertIn(
            "survey_task_issue_scopes",
            tables,
        )


if __name__ == "__main__":
    unittest.main()
