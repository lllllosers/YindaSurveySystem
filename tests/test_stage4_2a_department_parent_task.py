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


class Stage42ADepartmentParentTaskTestCase(
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
            / "stage42a.db"
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
                    "Stage 4.2A 测试项目",
                    "4.2A",
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
                    "Stage 4.2A 批次",
                    "S42A",
                ),
            )
            self.batch_id = int(
                batch.lastrowid
            )

            department = connection.execute(
                """
                SELECT
                    d.id,
                    d.organization_unit_uid,
                    d.name
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
                    d.organization_unit_uid,
                    d.name
                HAVING COUNT(
                    DISTINCT o.id
                ) >= 2
                ORDER BY d.id
                LIMIT 1
                """
            ).fetchone()

            if department is None:
                self.fail(
                    "正式主数据中没有找到至少包含两个"
                    "有分管范围水管所的基层处。"
                )

            self.department_id = int(
                department["id"]
            )
            self.department_uid = (
                department[
                    "organization_unit_uid"
                ]
            )

            scopes = connection.execute(
                """
                SELECT
                    cms.management_scope_uid,
                    o.organization_unit_uid
                FROM canal_management_scopes AS cms
                JOIN organization_units AS o
                  ON o.id = cms.organization_unit_id
                WHERE o.parent_id = ?
                  AND o.unit_type = 'water_office'
                  AND o.status = 'active'
                  AND cms.status = 'active'
                ORDER BY
                    o.sort_order,
                    o.id,
                    cms.sort_order,
                    cms.id
                """,
                (
                    self.department_id,
                ),
            ).fetchall()

            selected = []
            seen_offices = set()

            for row in scopes:
                owner_uid = row[
                    "organization_unit_uid"
                ]
                if owner_uid in seen_offices:
                    continue

                seen_offices.add(
                    owner_uid
                )
                selected.append(
                    row[
                        "management_scope_uid"
                    ]
                )

                if len(selected) == 2:
                    break

            self.scope_uids = tuple(
                selected
            )

            other = connection.execute(
                """
                SELECT
                    cms.management_scope_uid
                FROM canal_management_scopes AS cms
                JOIN organization_units AS o
                  ON o.id = cms.organization_unit_id
                WHERE o.unit_type = 'water_office'
                  AND o.status = 'active'
                  AND cms.status = 'active'
                  AND o.parent_id != ?
                ORDER BY cms.id
                LIMIT 1
                """,
                (
                    self.department_id,
                ),
            ).fetchone()

            self.other_scope_uid = (
                other[
                    "management_scope_uid"
                ]
                if other is not None
                else None
            )

        self.assertEqual(
            len(self.scope_uids),
            2,
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

    def _export_department(
        self,
        *,
        scope_uids=None,
        filename="处级父任务.ydtask",
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
                    self.department_id
                ),
                management_scope_uids=(
                    tuple(
                        self.scope_uids
                        if scope_uids is None
                        else scope_uids
                    )
                ),
                task_name=(
                    "基层处父任务"
                ),
                output_path=(
                    self.temp_root
                    / filename
                ),
                notes=(
                    "Stage 4.2A"
                ),
            )
        )

    def test_department_parent_task_can_cover_multiple_offices(
        self,
    ):
        result = self._export_department()

        contents = (
            load_survey_task_package(
                result.output_path
            )
        )

        assignment = contents.task[
            "assignment"
        ]

        self.assertEqual(
            assignment[
                "target_unit_type"
            ],
            "department",
        )
        self.assertEqual(
            assignment[
                "department_uid"
            ],
            self.department_uid,
        )
        self.assertEqual(
            assignment[
                "organization_unit_uid"
            ],
            self.department_uid,
        )

        scope_owner_uids = {
            item[
                "organization_unit_uid"
            ]
            for item in contents.management_scopes
        }

        self.assertEqual(
            len(scope_owner_uids),
            2,
        )

        issue = get_issued_survey_task(
            result.task_uid
        )

        self.assertEqual(
            issue[
                "target_unit_type"
            ],
            "department",
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

    def test_department_task_rejects_scope_from_other_department(
        self,
    ):
        if self.other_scope_uid is None:
            self.skipTest(
                "正式主数据没有其他处可用于越权测试。"
            )

        with self.assertRaisesRegex(
            ValueError,
            "不属于当前管理单位",
        ):
            self._export_department(
                scope_uids=(
                    self.scope_uids[0],
                    self.other_scope_uid,
                ),
                filename=(
                    "越权任务.ydtask"
                ),
            )

    def test_direct_office_task_remains_supported(
        self,
    ):
        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    cms.management_scope_uid,
                    cms.organization_unit_id
                FROM canal_management_scopes AS cms
                JOIN organization_units AS o
                  ON o.id = cms.organization_unit_id
                WHERE o.parent_id = ?
                  AND o.unit_type = 'water_office'
                  AND o.status = 'active'
                  AND cms.status = 'active'
                ORDER BY cms.id
                LIMIT 1
                """,
                (
                    self.department_id,
                ),
            ).fetchone()

        result = export_survey_task_package(
            SurveyTaskExportRequest(
                project_id=(
                    self.project_id
                ),
                survey_batch_id=(
                    self.batch_id
                ),
                organization_unit_id=int(
                    row[
                        "organization_unit_id"
                    ]
                ),
                management_scope_uids=(
                    row[
                        "management_scope_uid"
                    ],
                ),
                task_name=(
                    "兼容所级任务"
                ),
                output_path=(
                    self.temp_root
                    / "所级任务.ydtask"
                ),
            )
        )

        contents = (
            load_survey_task_package(
                result.output_path
            )
        )

        self.assertEqual(
            contents.task[
                "assignment"
            ][
                "target_unit_type"
            ],
            "water_office",
        )


if __name__ == "__main__":
    unittest.main()
