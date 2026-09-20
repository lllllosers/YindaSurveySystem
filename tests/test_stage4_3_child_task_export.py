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
from services.survey_child_task_package import (
    ChildSurveyTaskExportRequest,
    export_child_survey_task_package,
)
from services.survey_task_issue_history import (
    get_issued_survey_task,
)
from services.survey_task_package import (
    SurveyTaskExportRequest,
    export_survey_task_package,
)
from services.survey_task_package_reader import (
    load_survey_task_package,
)
from services.survey_task_workspace import (
    get_current_task_workspace,
    receive_survey_task_package,
)


class Stage43ChildTaskExportTestCase(
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

        self.center_dir = (
            self.temp_root
            / "center"
            / "local_data"
        )
        self.center_db = (
            self.center_dir
            / "center.db"
        )

        self.department_dir = (
            self.temp_root
            / "department"
            / "local_data"
        )
        self.department_db = (
            self.department_dir
            / "department.db"
        )

        self.office_dir = (
            self.temp_root
            / "office"
            / "local_data"
        )
        self.office_db = (
            self.office_dir
            / "office.db"
        )

        self.parent_package = (
            self.temp_root
            / "parent.ydtask"
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

    def _prepare_parent_workspace(self):
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
                    "Stage 4.3 项目",
                    "4.3",
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
                    "Stage 4.3 批次",
                    "S43",
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
                 AND o.unit_type = 'water_office'
                 AND o.status = 'active'
                JOIN canal_management_scopes AS cms
                  ON cms.organization_unit_id = o.id
                 AND cms.status = 'active'
                WHERE d.unit_type = 'department'
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
                    "测试需要至少包含两个"
                    "有分管范围水管所的基层处。"
                )

            department_id = int(
                department[
                    "id"
                ]
            )

            scope_rows = (
                connection.execute(
                    """
                    SELECT
                        cms.management_scope_uid,
                        cms.organization_unit_id,
                        o.organization_unit_uid,
                        o.name AS organization_name
                    FROM canal_management_scopes
                        AS cms
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
            )

            by_office = {}

            for row in scope_rows:
                office_uid = row[
                    "organization_unit_uid"
                ]
                by_office.setdefault(
                    office_uid,
                    {
                        "organization_unit_id": int(
                            row[
                                "organization_unit_id"
                            ]
                        ),
                        "organization_name": row[
                            "organization_name"
                        ],
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
                    "测试需要两个有分管范围的水管所。"
                )

            first_office = offices[0]
            second_office = offices[1]

            selected_parent_scopes = (
                first_office[
                    "scope_uids"
                ][:2]
                + second_office[
                    "scope_uids"
                ][:1]
            )

            if not first_office[
                "scope_uids"
            ]:
                self.fail(
                    "第一个水管所没有可测试 scope。"
                )

            outside = (
                connection.execute(
                    """
                    SELECT
                        cms.management_scope_uid
                    FROM canal_management_scopes
                        AS cms
                    JOIN organization_units AS o
                      ON o.id =
                        cms.organization_unit_id
                    WHERE cms.status = 'active'
                      AND o.status = 'active'
                      AND o.unit_type =
                        'water_office'
                      AND cms.management_scope_uid
                        NOT IN (
                            SELECT
                                cms2.management_scope_uid
                            FROM canal_management_scopes
                                AS cms2
                            JOIN organization_units
                                AS o2
                              ON o2.id =
                                cms2.organization_unit_id
                            WHERE o2.parent_id = ?
                        )
                    ORDER BY cms.id
                    LIMIT 1
                    """,
                    (
                        department_id,
                    ),
                ).fetchone()
            )

        parent_result = (
            export_survey_task_package(
                SurveyTaskExportRequest(
                    project_id=project_id,
                    survey_batch_id=batch_id,
                    organization_unit_id=(
                        department_id
                    ),
                    management_scope_uids=tuple(
                        selected_parent_scopes
                    ),
                    task_name=(
                        "中心下发处级父任务"
                    ),
                    output_path=(
                        self.parent_package
                    ),
                )
            )
        )

        self._use_department()
        initialize_application_database()

        receive_survey_task_package(
            self.parent_package
        )

        current = (
            get_current_task_workspace()
        )

        first_office_uid = None

        with database.get_connection() as connection:
            first_office_row = (
                connection.execute(
                    """
                    SELECT
                        id,
                        organization_unit_uid
                    FROM organization_units
                    WHERE unit_type =
                        'water_office'
                      AND name = ?
                    LIMIT 1
                    """,
                    (
                        first_office[
                            "organization_name"
                        ],
                    ),
                ).fetchone()
            )

            second_office_row = (
                connection.execute(
                    """
                    SELECT
                        id,
                        organization_unit_uid
                    FROM organization_units
                    WHERE unit_type =
                        'water_office'
                      AND name = ?
                    LIMIT 1
                    """,
                    (
                        second_office[
                            "organization_name"
                        ],
                    ),
                ).fetchone()
            )

            first_office_uid = (
                first_office_row[
                    "organization_unit_uid"
                ]
            )

        first_scope_uids = tuple(
            item[
                "management_scope_uid"
            ]
            for item in current[
                "management_scopes"
            ]
            if item[
                "organization_unit_uid"
            ]
            == first_office_uid
        )

        second_office_uid = (
            second_office_row[
                "organization_unit_uid"
            ]
        )

        second_scope_uids = tuple(
            item[
                "management_scope_uid"
            ]
            for item in current[
                "management_scopes"
            ]
            if item[
                "organization_unit_uid"
            ]
            == second_office_uid
        )

        return {
            "parent_task_uid": (
                parent_result.task_uid
            ),
            "first_office_id": int(
                first_office_row[
                    "id"
                ]
            ),
            "first_office_uid": (
                first_office_uid
            ),
            "first_scope_uids": (
                first_scope_uids
            ),
            "second_office_id": int(
                second_office_row[
                    "id"
                ]
            ),
            "second_scope_uids": (
                second_scope_uids
            ),
            "outside_scope_uid": (
                outside[
                    "management_scope_uid"
                ]
                if outside is not None
                else None
            ),
        }

    def test_department_can_export_child_task(
        self,
    ):
        context = (
            self._prepare_parent_workspace()
        )

        child_path = (
            self.temp_root
            / "child.ydtask"
        )

        result = (
            export_child_survey_task_package(
                ChildSurveyTaskExportRequest(
                    organization_unit_id=(
                        context[
                            "first_office_id"
                        ]
                    ),
                    management_scope_uids=(
                        context[
                            "first_scope_uids"
                        ][:1]
                    ),
                    task_name=(
                        "处下发所级子任务"
                    ),
                    output_path=(
                        child_path
                    ),
                )
            )
        )

        self.assertEqual(
            result.parent_task_uid,
            context[
                "parent_task_uid"
            ],
        )
        self.assertEqual(
            result.root_task_uid,
            context[
                "parent_task_uid"
            ],
        )
        self.assertEqual(
            result.task_depth,
            1,
        )

        contents = (
            load_survey_task_package(
                child_path
            )
        )

        self.assertEqual(
            contents.task[
                "lineage"
            ][
                "parent_task_uid"
            ],
            context[
                "parent_task_uid"
            ],
        )
        self.assertEqual(
            contents.task[
                "lineage"
            ][
                "root_task_uid"
            ],
            context[
                "parent_task_uid"
            ],
        )
        self.assertEqual(
            contents.task[
                "lineage"
            ][
                "depth"
            ],
            1,
        )
        self.assertEqual(
            contents.task[
                "assignment"
            ][
                "target_unit_type"
            ],
            "water_office",
        )

        child_scope_uids = {
            item[
                "management_scope_uid"
            ]
            for item in (
                contents.management_scopes
            )
        }

        self.assertEqual(
            child_scope_uids,
            set(
                context[
                    "first_scope_uids"
                ][:1]
            ),
        )

        issue = get_issued_survey_task(
            result.task_uid
        )

        self.assertEqual(
            issue[
                "parent_task_uid"
            ],
            context[
                "parent_task_uid"
            ],
        )
        self.assertEqual(
            issue[
                "root_task_uid"
            ],
            context[
                "parent_task_uid"
            ],
        )
        self.assertEqual(
            issue[
                "task_depth"
            ],
            1,
        )

    def test_child_scope_must_be_subset_of_parent(
        self,
    ):
        context = (
            self._prepare_parent_workspace()
        )

        if context[
            "outside_scope_uid"
        ] is None:
            self.skipTest(
                "没有找到父任务范围外的 scope。"
            )

        with self.assertRaisesRegex(
            ValueError,
            "必须完全来自父任务冻结范围",
        ):
            export_child_survey_task_package(
                ChildSurveyTaskExportRequest(
                    organization_unit_id=(
                        context[
                            "first_office_id"
                        ]
                    ),
                    management_scope_uids=(
                        context[
                            "first_scope_uids"
                        ][0],
                        context[
                            "outside_scope_uid"
                        ],
                    ),
                    task_name=(
                        "越权子任务"
                    ),
                    output_path=(
                        self.temp_root
                        / "outside.ydtask"
                    ),
                )
            )

    def test_child_cannot_take_another_office_scope(
        self,
    ):
        context = (
            self._prepare_parent_workspace()
        )

        self.assertTrue(
            context[
                "second_scope_uids"
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "只能包含目标水管所自己的",
        ):
            export_child_survey_task_package(
                ChildSurveyTaskExportRequest(
                    organization_unit_id=(
                        context[
                            "first_office_id"
                        ]
                    ),
                    management_scope_uids=(
                        context[
                            "second_scope_uids"
                        ][:1]
                    ),
                    task_name=(
                        "跨所子任务"
                    ),
                    output_path=(
                        self.temp_root
                        / "wrong_owner.ydtask"
                    ),
                )
            )

    def test_office_can_receive_child_task(
        self,
    ):
        context = (
            self._prepare_parent_workspace()
        )

        child_path = (
            self.temp_root
            / "office_receive.ydtask"
        )

        child = (
            export_child_survey_task_package(
                ChildSurveyTaskExportRequest(
                    organization_unit_id=(
                        context[
                            "first_office_id"
                        ]
                    ),
                    management_scope_uids=(
                        context[
                            "first_scope_uids"
                        ][:1]
                    ),
                    task_name=(
                        "所级调查任务"
                    ),
                    output_path=(
                        child_path
                    ),
                )
            )
        )

        self._use_office()
        initialize_application_database()

        receive_survey_task_package(
            child_path
        )

        current = (
            get_current_task_workspace()
        )

        self.assertEqual(
            current[
                "task_uid"
            ],
            child.task_uid,
        )
        self.assertEqual(
            current[
                "parent_task_uid"
            ],
            context[
                "parent_task_uid"
            ],
        )
        self.assertEqual(
            current[
                "root_task_uid"
            ],
            context[
                "parent_task_uid"
            ],
        )
        self.assertEqual(
            current[
                "task_depth"
            ],
            1,
        )
        self.assertEqual(
            current[
                "target_unit_type"
            ],
            "water_office",
        )


if __name__ == "__main__":
    unittest.main()
