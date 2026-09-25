import gc
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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
from services.survey_result_import_preflight import (
    preflight_survey_result_import,
)
from services.survey_result_import_history import (
    list_survey_result_import_history,
)
from services.survey_result_package import (
    SurveyResultExportRequest,
    export_survey_result_package,
)
from services.survey_progress import (
    get_engineering_progress,
)
from services.survey_task_package import (
    SurveyTaskExportRequest,
    export_survey_task_package,
)
from services.survey_task_tracking import (
    list_survey_task_tracking,
)
from services.survey_task_workspace import (
    receive_survey_task_package,
)


class Stage7MultiOfficeRoundTripTestCase(
    unittest.TestCase,
):
    """
    Stage 7.1 production-style round trip.

    One parent database:
        same project + same survey batch
        -> dispatch two independent office tasks

    Two child databases:
        receive their own .ydtask
        -> create one completed engineering survey each
        -> return one .ydresult each

    Parent database:
        preflight both
        -> import both sequentially
        -> verify they merge into the same project/batch
        -> verify task/scope provenance
        -> verify ledger/query aggregation
        -> verify duplicate imports are idempotent
    """

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

        self.child_databases = [
            {
                "data_dir": (
                    self.temp_root
                    / "child_a"
                    / "local_data"
                ),
                "db_path": (
                    self.temp_root
                    / "child_a"
                    / "local_data"
                    / "child_a.db"
                ),
            },
            {
                "data_dir": (
                    self.temp_root
                    / "child_b"
                    / "local_data"
                ),
                "db_path": (
                    self.temp_root
                    / "child_b"
                    / "local_data"
                    / "child_b.db"
                ),
            },
        ]

        self.task_paths = [
            self.temp_root
            / "office_a.ydtask",
            self.temp_root
            / "office_b.ydtask",
        ]
        self.result_paths = [
            self.temp_root
            / "office_a.ydresult",
            self.temp_root
            / "office_b.ydresult",
        ]

        self._build_parent_and_tasks()

        for index in range(2):
            self._build_child_result(
                index
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

    def _use_database(
        self,
        data_dir,
        db_path,
    ):
        database.DATA_DIR = Path(
            data_dir
        )
        database.DB_PATH = Path(
            db_path
        )

    def _use_parent(self):
        self._use_database(
            self.parent_data_dir,
            self.parent_db_path,
        )

    def _use_child(self, index):
        child = self.child_databases[
            index
        ]

        self._use_database(
            child["data_dir"],
            child["db_path"],
        )

    def _find_two_office_scopes(self):
        """
        Reuse seeded official master data instead of inventing
        test-only organization/canal identities.

        Pick the first active management scope belonging to each
        of two distinct active water offices.
        """

        with database.get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    office.id AS office_id,
                    office.organization_unit_uid
                        AS office_uid,
                    office.name AS office_name,

                    department.name
                        AS department_name,

                    cms.management_scope_uid,
                    cms.canal_unit_id,

                    canal.canal_unit_uid,
                    canal.name AS canal_name

                FROM canal_management_scopes
                    AS cms

                JOIN organization_units
                    AS office
                  ON office.id
                    = cms.organization_unit_id

                LEFT JOIN organization_units
                    AS department
                  ON department.id
                    = office.parent_id

                JOIN canal_units
                    AS canal
                  ON canal.id
                    = cms.canal_unit_id

                WHERE
                    cms.status = 'active'
                    AND office.status = 'active'
                    AND office.unit_type
                        = 'water_office'
                    AND canal.status = 'active'

                ORDER BY
                    CASE
                        WHEN office.sort_order > 0
                        THEN office.sort_order
                        ELSE 1000000 + office.id
                    END,
                    office.id,
                    cms.sort_order,
                    cms.id
                """
            ).fetchall()

        selected = []
        used_office_ids = set()

        for row in rows:
            office_id = int(
                row["office_id"]
            )

            if office_id in used_office_ids:
                continue

            selected.append(
                dict(row)
            )
            used_office_ids.add(
                office_id
            )

            if len(selected) == 2:
                break

        if len(selected) < 2:
            self.fail(
                "Stage 7.1 requires at least two active "
                "management offices with active management scopes."
            )

        return selected

    def _build_parent_and_tasks(self):
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
                    "Stage7多单位生产验证项目",
                    "STAGE7",
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
                    start_date,
                    status
                )
                VALUES (
                    ?, ?, ?, ?, 'active'
                )
                """,
                (
                    self.parent_project_id,
                    "Stage7多单位调查批次",
                    "STAGE7-2026",
                    "2026-09-19",
                ),
            )
            self.parent_batch_id = int(
                batch.lastrowid
            )

            identity = connection.execute(
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

        self.project_uid = (
            identity["project_uid"]
        )
        self.batch_uid = (
            identity[
                "survey_batch_uid"
            ]
        )

        self.office_scopes = (
            self._find_two_office_scopes()
        )
        self.tasks = []

        for index, office_scope in enumerate(
            self.office_scopes
        ):
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
                            int(
                                office_scope[
                                    "office_id"
                                ]
                            )
                        ),
                        management_scope_uids=(
                            (
                                office_scope[
                                    "management_scope_uid"
                                ],
                            )
                        ),
                        task_name=(
                            "Stage7-"
                            + office_scope[
                                "office_name"
                            ]
                            + "-调查任务"
                        ),
                        output_path=(
                            self.task_paths[
                                index
                            ]
                        ),
                        notes=(
                            "Stage 7.1 "
                            "multi-office round trip"
                        ),
                    )
                )
            )

            self.assertTrue(
                task_result.output_path.exists()
            )
            self.assertEqual(
                task_result.selected_management_scope_count,
                1,
            )

            self.tasks.append(
                {
                    "task_uid": (
                        task_result.task_uid
                    ),
                    "task_package_uid": (
                        task_result.package_uid
                    ),
                    "office_id": int(
                        office_scope[
                            "office_id"
                        ]
                    ),
                    "office_uid": (
                        office_scope[
                            "office_uid"
                        ]
                    ),
                    "office_name": (
                        office_scope[
                            "office_name"
                        ]
                    ),
                    "management_scope_uid": (
                        office_scope[
                            "management_scope_uid"
                        ]
                    ),
                    "canal_uid": (
                        office_scope[
                            "canal_unit_uid"
                        ]
                    ),
                    "task_path": (
                        self.task_paths[
                            index
                        ]
                    ),
                }
            )

        self.assertNotEqual(
            self.tasks[0]["office_uid"],
            self.tasks[1]["office_uid"],
        )
        self.assertNotEqual(
            self.tasks[0]["task_uid"],
            self.tasks[1]["task_uid"],
        )

        with database.get_connection() as connection:
            issue_count = connection.execute(
                """
                SELECT COUNT(*) AS value
                FROM survey_task_issues
                WHERE project_uid = ?
                  AND survey_batch_uid = ?
                """,
                (
                    self.project_uid,
                    self.batch_uid,
                ),
            ).fetchone()

        self.assertEqual(
            int(
                issue_count["value"]
            ),
            2,
        )

    def _build_child_result(
        self,
        index,
    ):
        self._use_child(
            index
        )
        initialize_application_database()

        task = self.tasks[
            index
        ]

        receive_result = (
            receive_survey_task_package(
                task["task_path"]
            )
        )

        self.assertFalse(
            receive_result.already_received
        )
        self.assertEqual(
            receive_result.task_uid,
            task["task_uid"],
        )
        self.assertEqual(
            receive_result.selected_management_scope_count,
            1,
        )

        with database.get_connection() as connection:
            workspace = connection.execute(
                """
                SELECT
                    id,
                    task_uid,
                    project_id,
                    survey_batch_id,
                    organization_unit_id
                FROM survey_task_workspaces
                WHERE is_current = 1
                """
            ).fetchone()

            self.assertIsNotNone(
                workspace
            )
            self.assertEqual(
                workspace["task_uid"],
                task["task_uid"],
            )

            scopes = connection.execute(
                """
                SELECT
                    management_scope_uid,
                    canal_unit_id,
                    canal_unit_uid
                FROM survey_task_workspace_scopes
                WHERE task_workspace_id = ?
                ORDER BY sort_order, id
                """,
                (
                    int(
                        workspace["id"]
                    ),
                ),
            ).fetchall()

            self.assertEqual(
                len(scopes),
                1,
            )

            scope = scopes[0]

            self.assertEqual(
                scope[
                    "management_scope_uid"
                ],
                task[
                    "management_scope_uid"
                ],
            )
            self.assertEqual(
                scope[
                    "canal_unit_uid"
                ],
                task[
                    "canal_uid"
                ],
            )

            form = connection.execute(
                """
                SELECT
                    fv.id AS form_version_id,
                    fd.asset_type
                FROM form_definitions AS fd
                JOIN form_versions AS fv
                  ON fv.form_definition_id = fd.id
                WHERE
                    fd.series = 'series_2'
                    AND fd.record_type
                        = 'engineering'
                    AND fd.is_enabled = 1
                    AND fv.is_current = 1
                ORDER BY
                    fd.sort_order,
                    fd.id,
                    fv.id
                LIMIT 1
                """
            ).fetchone()

            self.assertIsNotNone(
                form
            )

            business_code = (
                f"STAGE7-{index + 1:02d}-001"
            )
            asset_name = (
                f"Stage7-{task['office_name']}-测试工程"
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
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, 'active'
                )
                """,
                (
                    receive_result.project_id,
                    asset_name,
                    form["asset_type"],
                    receive_result.organization_unit_id,
                    int(
                        scope[
                            "canal_unit_id"
                        ]
                    ),
                    business_code,
                    receive_result.survey_batch_id,
                ),
            )

            asset_id = int(
                asset.lastrowid
            )

            grade = (
                "A"
                if index == 0
                else "B"
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
                    survey_comment,
                    record_status,
                    record_data_json
                )
                VALUES (
                    ?, ?, ?, 'engineering',
                    ?, ?, ?, ?, ?, ?, ?, ?,
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
                        scope[
                            "canal_unit_id"
                        ]
                    ),
                    asset_id,
                    task[
                        "management_scope_uid"
                    ],
                    business_code,
                    (
                        f"2026-09-{19 + index:02d}"
                    ),
                    grade,
                    "Stage 7.1 多单位回收测试",
                    json.dumps(
                        {
                            "stage": "7.1",
                            "office_uid": (
                                task[
                                    "office_uid"
                                ]
                            ),
                            "child_index": index,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

            record_id = int(
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
                    record_id,
                    "STAGE7-01",
                    "生产验证",
                    "多单位成果回收",
                    grade,
                    "Stage 7.1",
                    task[
                        "office_name"
                    ],
                ),
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
                    record_id,
                ),
            ).fetchone()

        self.assertEqual(
            provenance[
                "source_task_uid"
            ],
            task["task_uid"],
        )
        self.assertEqual(
            provenance[
                "source_management_scope_uid"
            ],
            task[
                "management_scope_uid"
            ],
        )

        result = (
            export_survey_result_package(
                SurveyResultExportRequest(
                    project_id=(
                        receive_result.project_id
                    ),
                    survey_batch_id=(
                        receive_result.survey_batch_id
                    ),
                    survey_record_ids=(
                        record_id,
                    ),
                    output_path=(
                        self.result_paths[
                            index
                        ]
                    ),
                    result_name=(
                        f"Stage7-{task['office_name']}-调查成果"
                    ),
                )
            )
        )

        self.assertTrue(
            result.output_path.exists()
        )
        self.assertEqual(
            result.survey_record_count,
            1,
        )

        task[
            "record_uid"
        ] = (
            provenance[
                "survey_record_uid"
            ]
        )
        task[
            "business_code"
        ] = business_code
        task[
            "grade"
        ] = grade
        task[
            "result_path"
        ] = (
            self.result_paths[
                index
            ]
        )

    def _fake_backup(
        self,
        suffix,
    ):
        path = (
            self.parent_data_dir
            / "backups"
            / f"stage7_{suffix}.db"
        )
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.write_bytes(
            b"stage7-backup"
        )
        return path

    @patch(
        "services.survey_result_import."
        "create_database_backup"
    )
    def test_two_office_results_merge_and_repeat_import_is_idempotent(
        self,
        mock_backup,
    ):
        self._use_parent()

        backup_counter = {
            "value": 0,
        }

        def backup_side_effect(*args, **kwargs):
            backup_counter["value"] += 1
            return self._fake_backup(
                backup_counter[
                    "value"
                ]
            )

        mock_backup.side_effect = (
            backup_side_effect
        )

        initial_tracking = (
            list_survey_task_tracking(
                project_id=(
                    self.parent_project_id
                ),
                survey_batch_id=(
                    self.parent_batch_id
                ),
            )
        )

        self.assertEqual(
            len(
                initial_tracking
            ),
            2,
        )
        self.assertTrue(
            all(
                item.returned_record_count
                == 0
                for item in initial_tracking
            )
        )
        self.assertTrue(
            all(
                item.status_text
                == "待回收"
                for item in initial_tracking
            )
        )

        # -----------------------------------------------------
        # 1. Both packages independently pass preflight.
        # -----------------------------------------------------
        for task in self.tasks:
            report = (
                preflight_survey_result_import(
                    task[
                        "result_path"
                    ]
                )
            )

            self.assertTrue(
                report.can_import,
                report.format_text(),
            )
            self.assertEqual(
                report.new_records,
                1,
            )
            self.assertEqual(
                report.new_assets,
                1,
            )

        # -----------------------------------------------------
        # 2. Sequential import into the same parent project/batch.
        # -----------------------------------------------------
        first_results = []

        for task in self.tasks:
            result = (
                import_survey_result_package(
                    task[
                        "result_path"
                    ]
                )
            )

            self.assertFalse(
                result.already_imported
            )
            self.assertEqual(
                result.imported_records,
                1,
            )
            self.assertEqual(
                result.imported_assets,
                1,
            )
            self.assertEqual(
                result.imported_inspections,
                1,
            )

            first_results.append(
                result
            )

        # -----------------------------------------------------
        # 3. Parent contains one shared project/batch and both results.
        # -----------------------------------------------------
        with database.get_connection() as connection:
            identity_counts = connection.execute(
                """
                SELECT
                    (
                        SELECT COUNT(*)
                        FROM projects
                        WHERE project_uid = ?
                    ) AS project_count,

                    (
                        SELECT COUNT(*)
                        FROM survey_batches
                        WHERE survey_batch_uid = ?
                    ) AS batch_count
                """,
                (
                    self.project_uid,
                    self.batch_uid,
                ),
            ).fetchone()

            imported_rows = connection.execute(
                """
                SELECT
                    sr.survey_record_uid,
                    sr.business_code,
                    sr.overall_grade,
                    sr.source_task_uid,
                    sr.source_management_scope_uid,
                    p.project_uid,
                    sb.survey_batch_uid,
                    office.organization_unit_uid
                        AS office_uid

                FROM survey_records AS sr

                JOIN projects AS p
                  ON p.id = sr.project_id

                JOIN survey_batches AS sb
                  ON sb.id
                    = sr.survey_batch_id

                JOIN organization_units
                    AS office
                  ON office.id
                    = sr.organization_unit_id

                WHERE
                    p.project_uid = ?
                    AND sb.survey_batch_uid = ?
                    AND sr.record_status != 'void'

                ORDER BY sr.id
                """,
                (
                    self.project_uid,
                    self.batch_uid,
                ),
            ).fetchall()

            import_log_count = connection.execute(
                """
                SELECT COUNT(*) AS value
                FROM survey_result_imports
                WHERE project_uid = ?
                  AND survey_batch_uid = ?
                """,
                (
                    self.project_uid,
                    self.batch_uid,
                ),
            ).fetchone()

        self.assertEqual(
            int(
                identity_counts[
                    "project_count"
                ]
            ),
            1,
        )
        self.assertEqual(
            int(
                identity_counts[
                    "batch_count"
                ]
            ),
            1,
        )
        self.assertEqual(
            len(imported_rows),
            2,
        )
        self.assertEqual(
            int(
                import_log_count[
                    "value"
                ]
            ),
            2,
        )

        expected_provenance = {
            (
                task["record_uid"],
                task["task_uid"],
                task[
                    "management_scope_uid"
                ],
                task["office_uid"],
            )
            for task in self.tasks
        }

        actual_provenance = {
            (
                row[
                    "survey_record_uid"
                ],
                row[
                    "source_task_uid"
                ],
                row[
                    "source_management_scope_uid"
                ],
                row[
                    "office_uid"
                ],
            )
            for row in imported_rows
        }

        self.assertEqual(
            actual_provenance,
            expected_provenance,
        )

        # -----------------------------------------------------
        # 4. Ledger and global query both aggregate both offices.
        # -----------------------------------------------------
        query_rows = (
            database
            .get_engineering_survey_query_records(
                project_id=(
                    self.parent_project_id
                ),
                survey_batch_id=(
                    self.parent_batch_id
                ),
            )
        )

        ledger_rows = (
            database.get_engineering_assets(
                project_id=(
                    self.parent_project_id
                ),
                survey_batch_id=(
                    self.parent_batch_id
                ),
            )
        )

        self.assertEqual(
            len(query_rows),
            2,
        )
        self.assertEqual(
            len(ledger_rows),
            2,
        )

        self.assertEqual(
            {
                row[
                    "business_code"
                ]
                for row in query_rows
            },
            {
                task[
                    "business_code"
                ]
                for task in self.tasks
            },
        )
        self.assertEqual(
            {
                row[
                    "office_name"
                ]
                for row in query_rows
            },
            {
                task[
                    "office_name"
                ]
                for task in self.tasks
            },
        )
        self.assertEqual(
            {
                row[
                    "overall_grade"
                ]
                for row in ledger_rows
            },
            {
                "A",
                "B",
            },
        )

        # -----------------------------------------------------
        # 5. Re-importing either package is idempotent.
        # -----------------------------------------------------
        for task in self.tasks:
            result = (
                import_survey_result_package(
                    task[
                        "result_path"
                    ]
                )
            )

            self.assertTrue(
                result.already_imported
            )

        with database.get_connection() as connection:
            final_counts = connection.execute(
                """
                SELECT
                    (
                        SELECT COUNT(*)
                        FROM survey_records AS sr
                        JOIN projects AS p
                          ON p.id = sr.project_id
                        JOIN survey_batches AS sb
                          ON sb.id = sr.survey_batch_id
                        WHERE
                            p.project_uid = ?
                            AND sb.survey_batch_uid = ?
                            AND sr.record_status != 'void'
                    ) AS records,

                    (
                        SELECT COUNT(*)
                        FROM survey_result_imports
                        WHERE project_uid = ?
                          AND survey_batch_uid = ?
                    ) AS imports
                """,
                (
                    self.project_uid,
                    self.batch_uid,
                    self.project_uid,
                    self.batch_uid,
                ),
            ).fetchone()

        self.assertEqual(
            int(
                final_counts[
                    "records"
                ]
            ),
            2,
        )
        self.assertEqual(
            int(
                final_counts[
                    "imports"
                ]
            ),
            2,
        )

        task_tracking = (
            list_survey_task_tracking(
                project_id=(
                    self.parent_project_id
                ),
                survey_batch_id=(
                    self.parent_batch_id
                ),
            )
        )

        self.assertEqual(
            len(
                task_tracking
            ),
            2,
        )
        self.assertGreater(
            task_tracking[0].issue_id,
            task_tracking[1].issue_id,
        )
        self.assertEqual(
            {
                item.task_uid
                for item in task_tracking
            },
            {
                task["task_uid"]
                for task in self.tasks
            },
        )
        self.assertTrue(
            all(
                item.returned_record_count
                == 1
                for item in task_tracking
            )
        )
        self.assertTrue(
            all(
                item.status_text
                == "已有成果返回"
                for item in task_tracking
            )
        )

        first_office_tracking = (
            list_survey_task_tracking(
                project_id=(
                    self.parent_project_id
                ),
                survey_batch_id=(
                    self.parent_batch_id
                ),
                organization_uid=(
                    self.tasks[0][
                        "office_uid"
                    ]
                ),
            )
        )

        self.assertEqual(
            len(
                first_office_tracking
            ),
            1,
        )
        self.assertEqual(
            first_office_tracking[
                0
            ].task_uid,
            self.tasks[0][
                "task_uid"
            ],
        )

        # Result-receive history must classify both packages
        # by frozen task source and keep newest-first ordering.
        history = list_survey_result_import_history(
            project_id=(
                self.parent_project_id
            ),
            survey_batch_id=(
                self.parent_batch_id
            ),
        )

        self.assertEqual(
            len(history),
            2,
        )
        self.assertGreater(
            history[0].import_id,
            history[1].import_id,
        )
        self.assertEqual(
            {
                uid
                for item in history
                for uid in item.organization_uids
            },
            {
                task["office_uid"]
                for task in self.tasks
            },
        )
        self.assertTrue(
            all(
                item.records_total == 1
                for item in history
            )
        )
        self.assertTrue(
            all(
                item.status_text == "已导入"
                for item in history
            )
        )

        first_office_history = (
            list_survey_result_import_history(
                project_id=(
                    self.parent_project_id
                ),
                survey_batch_id=(
                    self.parent_batch_id
                ),
                organization_uid=(
                    self.tasks[0][
                        "office_uid"
                    ]
                ),
            )
        )

        self.assertEqual(
            len(
                first_office_history
            ),
            1,
        )
        self.assertIn(
            self.tasks[0][
                "office_uid"
            ],
            first_office_history[
                0
            ].organization_uids,
        )

        # Only the two first-time imports create backups.
        self.assertEqual(
            mock_backup.call_count,
            2,
        )

        for call in mock_backup.call_args_list:
            self.assertEqual(
                call.kwargs.get("reason"),
                "pre_result_import",
            )
            self.assertFalse(
                call.kwargs.get("skip_if_unchanged")
            )

    @patch(
        "services.survey_result_import."
        "create_database_backup"
    )
    def test_partial_then_complete_multi_office_return_updates_all_views(
        self,
        mock_backup,
    ):
        """
        Production acceptance sequence:

        1. two tasks have been dispatched;
        2. only office A returns first;
        3. parent views must show one returned / one pending;
        4. office B returns later;
        5. task tracking, result history, DataQuery,
           engineering ledger and Home progress must converge
           to the same two-record state.
        """

        self._use_parent()

        backup_counter = {
            "value": 0,
        }

        def backup_side_effect(
            *args,
            **kwargs,
        ):
            backup_counter[
                "value"
            ] += 1

            return self._fake_backup(
                "acceptance_"
                + str(
                    backup_counter[
                        "value"
                    ]
                )
            )

        mock_backup.side_effect = (
            backup_side_effect
        )

        # -----------------------------------------------------
        # A. Before any result returns: both tasks are pending.
        # -----------------------------------------------------
        before_tracking = (
            list_survey_task_tracking(
                project_id=(
                    self.parent_project_id
                ),
                survey_batch_id=(
                    self.parent_batch_id
                ),
            )
        )

        self.assertEqual(
            len(
                before_tracking
            ),
            2,
        )
        self.assertEqual(
            {
                item.status_text
                for item in before_tracking
            },
            {
                "待回收",
            },
        )

        # -----------------------------------------------------
        # B. Only office A returns.
        # -----------------------------------------------------
        first_result = (
            import_survey_result_package(
                self.tasks[
                    0
                ][
                    "result_path"
                ]
            )
        )

        self.assertFalse(
            first_result.already_imported
        )
        self.assertEqual(
            first_result.imported_records,
            1,
        )

        partial_tracking = (
            list_survey_task_tracking(
                project_id=(
                    self.parent_project_id
                ),
                survey_batch_id=(
                    self.parent_batch_id
                ),
            )
        )

        partial_status_by_task = {
            item.task_uid:
                (
                    item.status_text,
                    item.returned_record_count,
                )
            for item in partial_tracking
        }

        self.assertEqual(
            partial_status_by_task[
                self.tasks[
                    0
                ][
                    "task_uid"
                ]
            ],
            (
                "已有成果返回",
                1,
            ),
        )
        self.assertEqual(
            partial_status_by_task[
                self.tasks[
                    1
                ][
                    "task_uid"
                ]
            ],
            (
                "待回收",
                0,
            ),
        )

        partial_history = (
            list_survey_result_import_history(
                project_id=(
                    self.parent_project_id
                ),
                survey_batch_id=(
                    self.parent_batch_id
                ),
            )
        )

        self.assertEqual(
            len(
                partial_history
            ),
            1,
        )
        self.assertEqual(
            partial_history[
                0
            ].records_total,
            1,
        )
        self.assertIn(
            self.tasks[
                0
            ][
                "office_uid"
            ],
            partial_history[
                0
            ].organization_uids,
        )

        partial_query = (
            database
            .get_engineering_survey_query_records(
                project_id=(
                    self.parent_project_id
                ),
                survey_batch_id=(
                    self.parent_batch_id
                ),
            )
        )

        partial_ledger = (
            database.get_engineering_assets(
                project_id=(
                    self.parent_project_id
                ),
                survey_batch_id=(
                    self.parent_batch_id
                ),
            )
        )

        partial_progress = (
            get_engineering_progress(
                self.parent_project_id,
                self.parent_batch_id,
            )
        )

        self.assertEqual(
            len(
                partial_query
            ),
            1,
        )
        self.assertEqual(
            len(
                partial_ledger
            ),
            1,
        )
        self.assertEqual(
            partial_progress[
                "total_records"
            ],
            1,
        )
        self.assertEqual(
            partial_progress[
                "completed_records"
            ],
            1,
        )
        self.assertEqual(
            partial_progress[
                "draft_records"
            ],
            0,
        )
        self.assertEqual(
            partial_progress[
                "grades"
            ][
                "A"
            ],
            1,
        )
        self.assertEqual(
            partial_progress[
                "grades"
            ][
                "B"
            ],
            0,
        )

        # -----------------------------------------------------
        # C. Office B returns later.
        # -----------------------------------------------------
        second_result = (
            import_survey_result_package(
                self.tasks[
                    1
                ][
                    "result_path"
                ]
            )
        )

        self.assertFalse(
            second_result.already_imported
        )
        self.assertEqual(
            second_result.imported_records,
            1,
        )

        final_tracking = (
            list_survey_task_tracking(
                project_id=(
                    self.parent_project_id
                ),
                survey_batch_id=(
                    self.parent_batch_id
                ),
            )
        )

        final_history = (
            list_survey_result_import_history(
                project_id=(
                    self.parent_project_id
                ),
                survey_batch_id=(
                    self.parent_batch_id
                ),
            )
        )

        final_query = (
            database
            .get_engineering_survey_query_records(
                project_id=(
                    self.parent_project_id
                ),
                survey_batch_id=(
                    self.parent_batch_id
                ),
            )
        )

        final_ledger = (
            database.get_engineering_assets(
                project_id=(
                    self.parent_project_id
                ),
                survey_batch_id=(
                    self.parent_batch_id
                ),
            )
        )

        final_progress = (
            get_engineering_progress(
                self.parent_project_id,
                self.parent_batch_id,
            )
        )

        self.assertEqual(
            len(
                final_tracking
            ),
            2,
        )
        self.assertTrue(
            all(
                item.status_text
                == "已有成果返回"
                and item.returned_record_count
                == 1
                for item in final_tracking
            )
        )

        self.assertEqual(
            len(
                final_history
            ),
            2,
        )
        self.assertEqual(
            len(
                final_query
            ),
            2,
        )
        self.assertEqual(
            len(
                final_ledger
            ),
            2,
        )

        self.assertEqual(
            final_progress[
                "total_records"
            ],
            2,
        )
        self.assertEqual(
            final_progress[
                "completed_records"
            ],
            2,
        )
        self.assertEqual(
            final_progress[
                "draft_records"
            ],
            0,
        )
        self.assertEqual(
            final_progress[
                "grades"
            ][
                "A"
            ],
            1,
        )
        self.assertEqual(
            final_progress[
                "grades"
            ][
                "B"
            ],
            1,
        )
        self.assertAlmostEqual(
            final_progress[
                "completion_rate"
            ],
            100.0,
        )

        office_names = {
            office[
                "office_name"
            ]
            for department in final_progress[
                "departments"
            ]
            for office in department[
                "offices"
            ]
            if office[
                "total_records"
            ] > 0
        }

        self.assertEqual(
            office_names,
            {
                task[
                    "office_name"
                ]
                for task in self.tasks
            },
        )

        # -----------------------------------------------------
        # D. Re-import remains idempotent after the full merge.
        # -----------------------------------------------------
        repeated = (
            import_survey_result_package(
                self.tasks[
                    0
                ][
                    "result_path"
                ]
            )
        )

        self.assertTrue(
            repeated.already_imported
        )

        after_repeat_progress = (
            get_engineering_progress(
                self.parent_project_id,
                self.parent_batch_id,
            )
        )

        self.assertEqual(
            after_repeat_progress[
                "total_records"
            ],
            2,
        )

        # Only the two first-time imports create backups.
        self.assertEqual(
            mock_backup.call_count,
            2,
        )



if __name__ == "__main__":
    unittest.main()
