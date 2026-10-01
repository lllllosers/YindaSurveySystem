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
from services.survey_child_task_package import (
    ChildSurveyTaskExportRequest,
    export_child_survey_task_package,
)
from services.survey_department_aggregate import (
    export_current_department_aggregate_result_package,
    preview_current_department_aggregate,
)
from services.survey_result_import import (
    import_survey_result_package,
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
from services.survey_task_package import (
    SurveyTaskExportRequest,
    export_survey_task_package,
)
from services.survey_task_workspace import (
    get_current_task_workspace,
    receive_survey_task_package,
)


class Stage45CThreeLevelEndToEndTestCase(
    unittest.TestCase,
):
    def setUp(self):
        self.temp_directory = (
            tempfile.TemporaryDirectory()
        )
        self.root = Path(
            self.temp_directory.name
        )

        self.original_data_dir = (
            database.DATA_DIR
        )
        self.original_db_path = (
            database.DB_PATH
        )

        self.center_dir = (
            self.root
            / "center"
            / "local_data"
        )
        self.center_db = (
            self.center_dir
            / "center.db"
        )

        self.department_dir = (
            self.root
            / "department"
            / "local_data"
        )
        self.department_db = (
            self.department_dir
            / "department.db"
        )

        self.office1_dir = (
            self.root
            / "office1"
            / "local_data"
        )
        self.office1_db = (
            self.office1_dir
            / "office1.db"
        )

        self.office2_dir = (
            self.root
            / "office2"
            / "local_data"
        )
        self.office2_db = (
            self.office2_dir
            / "office2.db"
        )

        self.parent_path = (
            self.root
            / "center_to_department.ydtask"
        )
        self.child1_path = (
            self.root
            / "department_to_office1.ydtask"
        )
        self.child2_path = (
            self.root
            / "department_to_office2.ydtask"
        )
        self.office1_result_path = (
            self.root
            / "office1_result.ydresult"
        )
        self.office2_result_path = (
            self.root
            / "office2_result.ydresult"
        )
        self.aggregate_path = (
            self.root
            / "department_to_center.ydresult"
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

    def _use_center(self):
        database.DATA_DIR = (
            self.center_dir
        )
        database.DB_PATH = (
            self.center_db
        )

    def _use_department(self):
        database.DATA_DIR = (
            self.department_dir
        )
        database.DB_PATH = (
            self.department_db
        )

    def _use_office1(self):
        database.DATA_DIR = (
            self.office1_dir
        )
        database.DB_PATH = (
            self.office1_db
        )

    def _use_office2(self):
        database.DATA_DIR = (
            self.office2_dir
        )
        database.DB_PATH = (
            self.office2_db
        )

    def _prepare_center_parent_task(self):
        self._use_center()
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
                    "Stage 4.5C 项目",
                    "S45C",
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
                    "Stage 4.5C 批次",
                    "S45C",
                ),
            )
            batch_id = int(
                batch.lastrowid
            )

            department = connection.execute(
                """
                SELECT
                    d.id,
                    d.organization_unit_uid
                FROM organization_units AS d
                JOIN organization_units AS o
                  ON o.parent_id = d.id
                 AND o.unit_type =
                    'water_office'
                 AND o.status = 'active'
                JOIN canal_management_scopes
                    AS cms
                  ON cms.organization_unit_id =
                    o.id
                 AND cms.status = 'active'
                WHERE d.unit_type =
                    'department'
                  AND d.status = 'active'
                GROUP BY
                    d.id,
                    d.organization_unit_uid
                HAVING COUNT(
                    DISTINCT o.id
                ) >= 2
                ORDER BY d.id
                LIMIT 1
                """
            ).fetchone()

            if department is None:
                self.fail(
                    "Stage 4.5C 需要至少有两个"
                    "具备有效分管范围的下属水管所。"
                )

            department_id = int(
                department[
                    "id"
                ]
            )

            scope_rows = connection.execute(
                """
                SELECT
                    cms.management_scope_uid,
                    cms.organization_unit_id,
                    o.organization_unit_uid,
                    o.name AS organization_name
                FROM canal_management_scopes AS cms
                JOIN organization_units AS o
                  ON o.id =
                    cms.organization_unit_id
                WHERE o.parent_id = ?
                  AND o.unit_type =
                    'water_office'
                  AND o.status = 'active'
                  AND cms.status = 'active'
                ORDER BY
                    o.sort_order,
                    o.id,
                    cms.sort_order,
                    cms.id
                """,
                (
                    department_id,
                ),
            ).fetchall()

        by_office = {}

        for row in scope_rows:
            office_uid = (
                row[
                    "organization_unit_uid"
                ]
            )

            by_office.setdefault(
                office_uid,
                {
                    "center_office_id": int(
                        row[
                            "organization_unit_id"
                        ]
                    ),
                    "office_uid": (
                        office_uid
                    ),
                    "office_name": (
                        row[
                            "organization_name"
                        ]
                    ),
                    "scope_uids": [],
                },
            )[
                "scope_uids"
            ].append(
                row[
                    "management_scope_uid"
                ]
            )

        offices = list(
            by_office.values()
        )

        if len(offices) < 2:
            self.fail(
                "Stage 4.5C 未找到两个可用水管所。"
            )

        office1 = offices[0]
        office2 = offices[1]

        scope1_uid = (
            office1[
                "scope_uids"
            ][0]
        )
        scope2_uid = (
            office2[
                "scope_uids"
            ][0]
        )

        parent = (
            export_survey_task_package(
                SurveyTaskExportRequest(
                    project_id=(
                        project_id
                    ),
                    survey_batch_id=(
                        batch_id
                    ),
                    organization_unit_id=(
                        department_id
                    ),
                    management_scope_uids=(
                        scope1_uid,
                        scope2_uid,
                    ),
                    task_name=(
                        "中心下发处级父任务"
                    ),
                    output_path=(
                        self.parent_path
                    ),
                )
            )
        )

        return {
            "project_id": project_id,
            "batch_id": batch_id,
            "department_id": department_id,
            "parent_task_uid": (
                parent.task_uid
            ),
            "office1_uid": (
                office1[
                    "office_uid"
                ]
            ),
            "office2_uid": (
                office2[
                    "office_uid"
                ]
            ),
            "scope1_uid": (
                scope1_uid
            ),
            "scope2_uid": (
                scope2_uid
            ),
        }

    def _prepare_department_children(
        self,
        context,
    ):
        self._use_department()
        initialize_application_database()

        receive_survey_task_package(
            self.parent_path
        )

        workspace = (
            get_current_task_workspace()
        )

        self.assertEqual(
            workspace[
                "task_uid"
            ],
            context[
                "parent_task_uid"
            ],
        )

        self.assertEqual(
            workspace[
                "target_unit_type"
            ],
            "department",
        )

        with database.get_connection() as connection:
            office1 = connection.execute(
                """
                SELECT id
                FROM organization_units
                WHERE organization_unit_uid = ?
                """,
                (
                    context[
                        "office1_uid"
                    ],
                ),
            ).fetchone()

            office2 = connection.execute(
                """
                SELECT id
                FROM organization_units
                WHERE organization_unit_uid = ?
                """,
                (
                    context[
                        "office2_uid"
                    ],
                ),
            ).fetchone()

        child1 = (
            export_child_survey_task_package(
                ChildSurveyTaskExportRequest(
                    organization_unit_id=int(
                        office1[
                            "id"
                        ]
                    ),
                    management_scope_uids=(
                        context[
                            "scope1_uid"
                        ],
                    ),
                    task_name=(
                        "处分发所1子任务"
                    ),
                    output_path=(
                        self.child1_path
                    ),
                )
            )
        )

        child2 = (
            export_child_survey_task_package(
                ChildSurveyTaskExportRequest(
                    organization_unit_id=int(
                        office2[
                            "id"
                        ]
                    ),
                    management_scope_uids=(
                        context[
                            "scope2_uid"
                        ],
                    ),
                    task_name=(
                        "处分发所2子任务"
                    ),
                    output_path=(
                        self.child2_path
                    ),
                )
            )
        )

        context.update(
            {
                "child1_task_uid": (
                    child1.task_uid
                ),
                "child2_task_uid": (
                    child2.task_uid
                ),
            }
        )

        return context

    def _create_office_result(
        self,
        *,
        use_office,
        child_path,
        child_task_uid,
        scope_uid,
        output_path,
        asset_name,
        business_code,
    ):
        use_office()
        initialize_application_database()

        receive_survey_task_package(
            child_path
        )

        workspace = (
            get_current_task_workspace()
        )

        self.assertEqual(
            workspace[
                "task_uid"
            ],
            child_task_uid,
        )

        self.assertEqual(
            workspace[
                "target_unit_type"
            ],
            "water_office",
        )

        scope = next(
            item
            for item in workspace[
                "management_scopes"
            ]
            if item[
                "management_scope_uid"
            ]
            == scope_uid
        )

        with database.get_connection() as connection:
            form = connection.execute(
                """
                SELECT
                    fv.id AS form_version_id,
                    fd.asset_type
                FROM form_definitions AS fd
                JOIN form_versions AS fv
                  ON fv.form_definition_id =
                    fd.id
                WHERE fd.series =
                    'series_2'
                  AND fd.record_type =
                    'engineering'
                  AND fd.is_enabled = 1
                  AND fv.is_current = 1
                ORDER BY
                    fd.sort_order,
                    fd.id
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
                    int(
                        workspace[
                            "project_id"
                        ]
                    ),
                    asset_name,
                    form[
                        "asset_type"
                    ],
                    int(
                        workspace[
                            "organization_unit_id"
                        ]
                    ),
                    int(
                        scope[
                            "canal_unit_id"
                        ]
                    ),
                    business_code,
                    int(
                        workspace[
                            "survey_batch_id"
                        ]
                    ),
                ),
            )

            asset_id = int(
                asset.lastrowid
            )

            record = connection.execute(
                """
                INSERT INTO survey_records (
                    source_task_uid,
                    source_management_scope_uid,
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
                    record_status,
                    record_data_json
                )
                VALUES (
                    ?, ?, ?, ?, ?,
                    'engineering',
                    ?, ?, ?, ?, ?,
                    ?, 'completed', ?
                )
                """,
                (
                    child_task_uid,
                    scope_uid,
                    int(
                        workspace[
                            "project_id"
                        ]
                    ),
                    int(
                        workspace[
                            "survey_batch_id"
                        ]
                    ),
                    int(
                        form[
                            "form_version_id"
                        ]
                    ),
                    int(
                        workspace[
                            "organization_unit_id"
                        ]
                    ),
                    int(
                        scope[
                            "canal_unit_id"
                        ]
                    ),
                    asset_id,
                    business_code,
                    "2026-09-20",
                    "B",
                    json.dumps(
                        {
                            "stage": (
                                "4.5C"
                            ),
                            "source_task_uid": (
                                child_task_uid
                            ),
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

            record_id = int(
                record.lastrowid
            )

        result = (
            export_survey_result_package(
                SurveyResultExportRequest(
                    project_id=int(
                        workspace[
                            "project_id"
                        ]
                    ),
                    survey_batch_id=int(
                        workspace[
                            "survey_batch_id"
                        ]
                    ),
                    survey_record_ids=(
                        record_id,
                    ),
                    output_path=(
                        output_path
                    ),
                    result_name=(
                        f"{asset_name}成果"
                    ),
                    submission_task_uid=(
                        child_task_uid
                    ),
                )
            )
        )

        package = (
            load_survey_result_package(
                result.output_path
            )
        )

        self.assertEqual(
            package.result[
                "submission_task_uid"
            ],
            child_task_uid,
        )

        self.assertEqual(
            package.survey_records[
                0
            ][
                "source_task_uid"
            ],
            child_task_uid,
        )

        return result

    def test_center_department_two_offices_full_roundtrip(
        self,
    ):
        context = (
            self._prepare_center_parent_task()
        )

        context = (
            self._prepare_department_children(
                context
            )
        )

        office1_result = (
            self._create_office_result(
                use_office=(
                    self._use_office1
                ),
                child_path=(
                    self.child1_path
                ),
                child_task_uid=(
                    context[
                        "child1_task_uid"
                    ]
                ),
                scope_uid=(
                    context[
                        "scope1_uid"
                    ]
                ),
                output_path=(
                    self.office1_result_path
                ),
                asset_name=(
                    "Stage 4.5C 所1工程"
                ),
                business_code=(
                    "TMP-45C-01"
                ),
            )
        )

        office2_result = (
            self._create_office_result(
                use_office=(
                    self._use_office2
                ),
                child_path=(
                    self.child2_path
                ),
                child_task_uid=(
                    context[
                        "child2_task_uid"
                    ]
                ),
                scope_uid=(
                    context[
                        "scope2_uid"
                    ]
                ),
                output_path=(
                    self.office2_result_path
                ),
                asset_name=(
                    "Stage 4.5C 所2工程"
                ),
                business_code=(
                    "TMP-45C-02"
                ),
            )
        )

        # ---------------------------------------------
        # 两个所成果依次回到处端。
        # ---------------------------------------------
        self._use_department()

        for result in (
            office1_result,
            office2_result,
        ):
            report = (
                preflight_survey_result_import(
                    result.output_path
                )
            )

            self.assertTrue(
                report.can_import,
                report.format_text(),
            )

            import_survey_result_package(
                result.output_path
            )

        department_workspace = (
            get_current_task_workspace()
        )

        self.assertEqual(
            department_workspace[
                "task_uid"
            ],
            context[
                "parent_task_uid"
            ],
        )

        preview = (
            preview_current_department_aggregate()
        )

        self.assertEqual(
            preview.parent_task_uid,
            context[
                "parent_task_uid"
            ],
        )

        self.assertEqual(
            preview.record_count,
            2,
        )

        self.assertEqual(
            set(
                preview.source_task_uids
            ),
            {
                context[
                    "child1_task_uid"
                ],
                context[
                    "child2_task_uid"
                ],
            },
        )

        self.assertEqual(
            preview.source_office_count,
            2,
        )

        self.assertEqual(
            set(
                preview.management_scope_uids
            ),
            {
                context[
                    "scope1_uid"
                ],
                context[
                    "scope2_uid"
                ],
            },
        )

        aggregate = (
            export_current_department_aggregate_result_package(
                self.aggregate_path,
                result_name=(
                    "Stage 4.5C 处级汇总成果"
                ),
            )
        )

        aggregate_contents = (
            load_survey_result_package(
                aggregate.output_path
            )
        )

        self.assertEqual(
            aggregate_contents.result[
                "submission_task_uid"
            ],
            context[
                "parent_task_uid"
            ],
        )

        self.assertEqual(
            {
                item[
                    "source_task_uid"
                ]
                for item in (
                    aggregate_contents.survey_records
                )
            },
            {
                context[
                    "child1_task_uid"
                ],
                context[
                    "child2_task_uid"
                ],
            },
        )

        # ---------------------------------------------
        # 中心端没有 T2/T3 下发历史。
        # 但中心曾直接下发 T1，因此应按 T1 接收处级汇总。
        # ---------------------------------------------
        self._use_center()

        with database.get_connection() as connection:
            child_issue_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM survey_task_issues
                    WHERE task_uid IN (?, ?)
                    """,
                    (
                        context[
                            "child1_task_uid"
                        ],
                        context[
                            "child2_task_uid"
                        ],
                    ),
                ).fetchone()[0]
            )

        self.assertEqual(
            child_issue_count,
            0,
        )

        center_report = (
            preflight_survey_result_import(
                aggregate.output_path
            )
        )

        self.assertTrue(
            center_report.can_import,
            center_report.format_text(),
        )

        codes = {
            item.code
            for item in center_report.issues
        }

        self.assertIn(
            "AGGREGATE_SUBMISSION_AUTHORITY_VERIFIED",
            codes,
        )

        self.assertNotIn(
            "SOURCE_TASK_ISSUE_MISSING",
            codes,
        )

        import_survey_result_package(
            aggregate.output_path
        )

        with database.get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    source_task_uid,
                    source_management_scope_uid
                FROM survey_records
                WHERE source_task_uid IN (?, ?)
                ORDER BY
                    source_task_uid,
                    source_management_scope_uid
                """,
                (
                    context[
                        "child1_task_uid"
                    ],
                    context[
                        "child2_task_uid"
                    ],
                ),
            ).fetchall()

        self.assertEqual(
            len(
                rows
            ),
            2,
        )

        self.assertEqual(
            {
                row[
                    "source_task_uid"
                ]
                for row in rows
            },
            {
                context[
                    "child1_task_uid"
                ],
                context[
                    "child2_task_uid"
                ],
            },
        )

        self.assertEqual(
            {
                row[
                    "source_management_scope_uid"
                ]
                for row in rows
            },
            {
                context[
                    "scope1_uid"
                ],
                context[
                    "scope2_uid"
                ],
            },
        )


if __name__ == "__main__":
    unittest.main()
