import gc
import json
import sys
import tempfile
import unittest
from pathlib import Path


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
from services.survey_child_task_package import (
    ChildSurveyTaskExportRequest,
    export_child_survey_task_package,
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


class Stage44ASubmissionEnvelopeTestCase(
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
            / "aggregate.ydresult"
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

    def _prepare_three_level_chain(self):
        # -------------------------------------------------
        # 1. 中心创建处级父任务 T1
        # -------------------------------------------------
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
                    "Stage 4.4A 项目",
                    "S44A",
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
                    "Stage 4.4A 批次",
                    "S44A",
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
                 AND o.unit_type = 'water_office'
                 AND o.status = 'active'
                JOIN canal_management_scopes AS cms
                  ON cms.organization_unit_id = o.id
                 AND cms.status = 'active'
                WHERE d.unit_type = 'department'
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
                    "正式主数据中没有可用于测试的处/所分管范围。"
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

        parent = (
            export_survey_task_package(
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
        )

        # -------------------------------------------------
        # 2. 处接收 T1，并派生所级子任务 T2
        # -------------------------------------------------
        self._use_department()
        initialize_application_database()

        receive_survey_task_package(
            self.parent_path
        )

        department_workspace = (
            get_current_task_workspace()
        )

        self.assertEqual(
            department_workspace[
                "task_uid"
            ],
            parent.task_uid,
        )
        self.assertEqual(
            department_workspace[
                "target_unit_type"
            ],
            "department",
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
                SELECT
                    id,
                    organization_unit_uid
                FROM organization_units
                WHERE organization_unit_uid = ?
                """,
                (
                    parent_scope[
                        "organization_unit_uid"
                    ],
                ),
            ).fetchone()

            if office is None:
                self.fail(
                    "处端找不到父任务 scope 对应水管所。"
                )

            department_office_id = int(
                office[
                    "id"
                ]
            )

        child = (
            export_child_survey_task_package(
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
        )

        return {
            "parent_task_uid": (
                parent.task_uid
            ),
            "child_task_uid": (
                child.task_uid
            ),
            "scope_uid": scope_uid,
        }

    def _create_office_result(
        self,
        context,
    ):
        # -------------------------------------------------
        # 3. 所在独立 local_data 中接收 T2 并形成真实调查记录。
        #
        # 这里不能在处库直接伪造 source_task_uid=T2 的记录，
        # 因为处库当前 workspace 是 T1，数据库触发器会正确阻止。
        # -------------------------------------------------
        self._use_office()
        initialize_application_database()

        receive_survey_task_package(
            self.child_path
        )

        office_workspace = (
            get_current_task_workspace()
        )

        self.assertEqual(
            office_workspace[
                "task_uid"
            ],
            context[
                "child_task_uid"
            ],
        )
        self.assertEqual(
            office_workspace[
                "parent_task_uid"
            ],
            context[
                "parent_task_uid"
            ],
        )
        self.assertEqual(
            office_workspace[
                "target_unit_type"
            ],
            "water_office",
        )

        office_scope = next(
            item
            for item in office_workspace[
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
                WHERE fd.series = 'series_2'
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
                        office_workspace[
                            "project_id"
                        ]
                    ),
                    "逐级汇总测试工程",
                    form[
                        "asset_type"
                    ],
                    int(
                        office_workspace[
                            "organization_unit_id"
                        ]
                    ),
                    int(
                        office_scope[
                            "canal_unit_id"
                        ]
                    ),
                    "TMP-001",
                    int(
                        office_workspace[
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
                        office_workspace[
                            "project_id"
                        ]
                    ),
                    int(
                        office_workspace[
                            "survey_batch_id"
                        ]
                    ),
                    int(
                        form[
                            "form_version_id"
                        ]
                    ),
                    int(
                        office_workspace[
                            "organization_unit_id"
                        ]
                    ),
                    int(
                        office_scope[
                            "canal_unit_id"
                        ]
                    ),
                    asset_id,
                    "TMP-001",
                    "2026-09-20",
                    "B",
                    json.dumps(
                        {
                            "stage": (
                                "4.4A"
                            ),
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

            office_record_id = int(
                record.lastrowid
            )

        exported = (
            export_survey_result_package(
                SurveyResultExportRequest(
                    project_id=int(
                        office_workspace[
                            "project_id"
                        ]
                    ),
                    survey_batch_id=int(
                        office_workspace[
                            "survey_batch_id"
                        ]
                    ),
                    survey_record_ids=(
                        office_record_id,
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
        )

        return exported

    def test_parent_submission_allows_center_preflight(
        self,
    ):
        context = (
            self._prepare_three_level_chain()
        )

        office_result = (
            self._create_office_result(
                context
            )
        )

        # -------------------------------------------------
        # 4. 所成果 T2 -> 处。
        #    importer 会在事务内暂时挂起当前 T1 workspace，
        #    因此可保留 record.source_task_uid=T2；
        #    导入完成后 T1 仍恢复为当前 workspace。
        # -------------------------------------------------
        self._use_department()

        office_preflight = (
            preflight_survey_result_import(
                office_result.output_path
            )
        )

        self.assertTrue(
            office_preflight.can_import,
            office_preflight.format_text(),
        )

        import_survey_result_package(
            office_result.output_path
        )

        current_after_import = (
            get_current_task_workspace()
        )

        self.assertEqual(
            current_after_import[
                "task_uid"
            ],
            context[
                "parent_task_uid"
            ],
        )

        with database.get_connection() as connection:
            imported_record = connection.execute(
                """
                SELECT
                    id,
                    source_task_uid,
                    source_management_scope_uid
                FROM survey_records
                WHERE source_task_uid = ?
                  AND source_management_scope_uid = ?
                ORDER BY id
                LIMIT 1
                """,
                (
                    context[
                        "child_task_uid"
                    ],
                    context[
                        "scope_uid"
                    ],
                ),
            ).fetchone()

        self.assertIsNotNone(
            imported_record
        )
        self.assertEqual(
            imported_record[
                "source_task_uid"
            ],
            context[
                "child_task_uid"
            ],
        )

        # -------------------------------------------------
        # 5. 处基于当前事实形成针对父任务 T1 的汇总成果。
        #    submission=T1；record provenance 仍是 T2。
        # -------------------------------------------------
        aggregate = (
            export_survey_result_package(
                SurveyResultExportRequest(
                    project_id=int(
                        current_after_import[
                            "project_id"
                        ]
                    ),
                    survey_batch_id=int(
                        current_after_import[
                            "survey_batch_id"
                        ]
                    ),
                    survey_record_ids=(
                        int(
                            imported_record[
                                "id"
                            ]
                        ),
                    ),
                    output_path=(
                        self.aggregate_path
                    ),
                    result_name=(
                        "处级汇总成果"
                    ),
                    submission_task_uid=(
                        context[
                            "parent_task_uid"
                        ]
                    ),
                )
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
            contents.manifest[
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

        # -------------------------------------------------
        # 6. 中心没有下发过 T2，但下发过 T1。
        #    应按 T1 冻结 scope 验收，并保留 T2 来源事实。
        # -------------------------------------------------
        self._use_center()

        report = (
            preflight_survey_result_import(
                aggregate.output_path
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
            "AGGREGATE_SUBMISSION_AUTHORITY_VERIFIED",
            codes,
        )
        self.assertNotIn(
            "SOURCE_TASK_ISSUE_MISSING",
            codes,
        )


if __name__ == "__main__":
    unittest.main()
