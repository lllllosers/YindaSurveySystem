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


class Stage44BAutoDepartmentAggregateTestCase(
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

        self.office_dir = (
            self.root
            / "office"
            / "local_data"
        )
        self.office_db = (
            self.office_dir
            / "office.db"
        )

        self.parent_path = (
            self.root
            / "parent.ydtask"
        )
        self.child_path = (
            self.root
            / "child.ydtask"
        )
        self.office_result_path = (
            self.root
            / "office_result.ydresult"
        )
        self.aggregate_path = (
            self.root
            / "department_aggregate.ydresult"
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

    def _use_office(self):
        database.DATA_DIR = (
            self.office_dir
        )
        database.DB_PATH = (
            self.office_db
        )

    def _prepare_chain(self):
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
                    "Stage 4.4B 项目",
                    "S44B",
                ),
            )
            center_project_id = int(
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
                    center_project_id,
                    "Stage 4.4B 批次",
                    "S44B",
                ),
            )
            center_batch_id = int(
                batch.lastrowid
            )

            target = connection.execute(
                """
                SELECT
                    d.id AS department_id,
                    cms.management_scope_uid
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
                ORDER BY
                    d.sort_order,
                    d.id,
                    o.sort_order,
                    o.id,
                    cms.sort_order,
                    cms.id
                LIMIT 1
                """
            ).fetchone()

            if target is None:
                self.fail(
                    "没有可用于 Stage 4.4B 测试的处/所范围。"
                )

            department_id = int(
                target[
                    "department_id"
                ]
            )
            scope_uid = (
                target[
                    "management_scope_uid"
                ]
            )

        parent = export_survey_task_package(
            SurveyTaskExportRequest(
                project_id=(
                    center_project_id
                ),
                survey_batch_id=(
                    center_batch_id
                ),
                organization_unit_id=(
                    department_id
                ),
                management_scope_uids=(
                    scope_uid,
                ),
                task_name=(
                    "中心发处父任务"
                ),
                output_path=(
                    self.parent_path
                ),
            )
        )

        self._use_department()
        initialize_application_database()

        receive_survey_task_package(
            self.parent_path
        )

        department_workspace = (
            get_current_task_workspace()
        )

        parent_scope = next(
            item
            for item in department_workspace[
                "management_scopes"
            ]
            if item[
                "management_scope_uid"
            ]
            == scope_uid
        )

        with database.get_connection() as connection:
            office = connection.execute(
                """
                SELECT id
                FROM organization_units
                WHERE organization_unit_uid = ?
                """,
                (
                    parent_scope[
                        "organization_unit_uid"
                    ],
                ),
            ).fetchone()

            department_office_id = int(
                office[
                    "id"
                ]
            )

        child = export_child_survey_task_package(
            ChildSurveyTaskExportRequest(
                organization_unit_id=(
                    department_office_id
                ),
                management_scope_uids=(
                    scope_uid,
                ),
                task_name=(
                    "处分发所子任务"
                ),
                output_path=(
                    self.child_path
                ),
            )
        )

        return {
            "parent_task_uid": (
                parent.task_uid
            ),
            "child_task_uid": (
                child.task_uid
            ),
            "scope_uid": (
                scope_uid
            ),
        }

    def _make_office_result(
        self,
        context,
    ):
        self._use_office()
        initialize_application_database()

        receive_survey_task_package(
            self.child_path
        )

        workspace = (
            get_current_task_workspace()
        )

        scope = next(
            item
            for item in workspace[
                "management_scopes"
            ]
            if item[
                "management_scope_uid"
            ]
            == context[
                "scope_uid"
            ]
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
                    "Stage 4.4B 测试工程",
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
                    "TMP-44B",
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
                    context[
                        "child_task_uid"
                    ],
                    context[
                        "scope_uid"
                    ],
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
                    "TMP-44B",
                    "2026-09-20",
                    "B",
                    json.dumps(
                        {
                            "stage": (
                                "4.4B"
                            ),
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

            record_id = int(
                record.lastrowid
            )

        return export_survey_result_package(
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
                    self.office_result_path
                ),
                result_name=(
                    "水管所成果"
                ),
                submission_task_uid=(
                    context[
                        "child_task_uid"
                    ]
                ),
            )
        )

    def test_department_auto_aggregate_uses_current_parent_task(
        self,
    ):
        context = self._prepare_chain()

        office_result = (
            self._make_office_result(
                context
            )
        )

        self._use_department()

        report = (
            preflight_survey_result_import(
                office_result.output_path
            )
        )

        self.assertTrue(
            report.can_import,
            report.format_text(),
        )

        import_survey_result_package(
            office_result.output_path
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
            1,
        )
        self.assertEqual(
            preview.source_task_uids,
            (
                context[
                    "child_task_uid"
                ],
            ),
        )
        self.assertEqual(
            preview.management_scope_uids,
            (
                context[
                    "scope_uid"
                ],
            ),
        )

        aggregate = (
            export_current_department_aggregate_result_package(
                self.aggregate_path,
                result_name=(
                    "处级自动汇总成果"
                ),
            )
        )

        contents = (
            load_survey_result_package(
                aggregate.output_path
            )
        )

        self.assertEqual(
            contents.result[
                "submission_task_uid"
            ],
            context[
                "parent_task_uid"
            ],
        )
        self.assertEqual(
            contents.survey_records[
                0
            ][
                "source_task_uid"
            ],
            context[
                "child_task_uid"
            ],
        )

        self._use_center()

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


if __name__ == "__main__":
    unittest.main()
