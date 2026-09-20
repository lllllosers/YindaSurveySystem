import gc
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


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


class Stage42BDepartmentWorkspaceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_directory.name)
        self.original_data_dir = database.DATA_DIR
        self.original_db_path = database.DB_PATH
        self.source_data_dir = self.temp_root / "source" / "local_data"
        self.source_db_path = self.source_data_dir / "source.db"
        self.target_data_dir = self.temp_root / "target" / "local_data"
        self.target_db_path = self.target_data_dir / "target.db"
        self.package_path = self.temp_root / "处级父任务.ydtask"

    def tearDown(self):
        gc.collect()
        database.DATA_DIR = self.original_data_dir
        database.DB_PATH = self.original_db_path
        self.temp_directory.cleanup()

    def _use_source(self):
        database.DATA_DIR = self.source_data_dir
        database.DB_PATH = self.source_db_path

    def _use_target(self):
        database.DATA_DIR = self.target_data_dir
        database.DB_PATH = self.target_db_path

    def _build_department_task(self):
        self._use_source()
        initialize_application_database()

        with database.get_connection() as connection:
            project = connection.execute(
                "INSERT INTO projects (name, short_name, status) "
                "VALUES (?, ?, 'active')",
                ("Stage 4.2B 项目", "4.2B"),
            )
            project_id = int(project.lastrowid)

            batch = connection.execute(
                "INSERT INTO survey_batches "
                "(project_id, batch_name, batch_code, status) "
                "VALUES (?, ?, ?, 'active')",
                (project_id, "Stage 4.2B 批次", "S42B"),
            )
            batch_id = int(batch.lastrowid)

            department = connection.execute(
                """
                SELECT d.id, d.organization_unit_uid
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
                GROUP BY d.id, d.organization_unit_uid
                HAVING COUNT(DISTINCT o.id) >= 2
                ORDER BY d.id
                LIMIT 1
                """
            ).fetchone()

            if department is None:
                self.fail(
                    "测试需要至少包含两个有分管范围水管所的基层处。"
                )

            department_id = int(department["id"])
            department_uid = department["organization_unit_uid"]

            rows = connection.execute(
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
                ORDER BY o.sort_order, o.id, cms.sort_order, cms.id
                """,
                (department_id,),
            ).fetchall()

            selected = []
            owner_uids = []
            seen = set()

            for row in rows:
                owner_uid = row["organization_unit_uid"]
                if owner_uid in seen:
                    continue
                seen.add(owner_uid)
                owner_uids.append(owner_uid)
                selected.append(row["management_scope_uid"])
                if len(selected) == 2:
                    break

        result = export_survey_task_package(
            SurveyTaskExportRequest(
                project_id=project_id,
                survey_batch_id=batch_id,
                organization_unit_id=department_id,
                management_scope_uids=tuple(selected),
                task_name="基层处父任务",
                output_path=self.package_path,
            )
        )

        return {
            "task_uid": result.task_uid,
            "department_uid": department_uid,
            "scope_uids": tuple(selected),
            "owner_uids": tuple(owner_uids),
        }

    def test_department_parent_task_can_be_received(self):
        source = self._build_department_task()

        self._use_target()
        initialize_application_database()

        result = receive_survey_task_package(
            self.package_path
        )
        self.assertFalse(result.already_received)

        current = get_current_task_workspace()
        self.assertIsNotNone(current)
        self.assertEqual(current["task_uid"], source["task_uid"])
        self.assertEqual(current["target_unit_type"], "department")
        self.assertEqual(
            current["organization_unit_uid"],
            source["department_uid"],
        )
        self.assertEqual(
            current["root_task_uid"],
            source["task_uid"],
        )
        self.assertIsNone(current["parent_task_uid"])
        self.assertEqual(current["task_depth"], 0)

        scopes = current["management_scopes"]
        self.assertEqual(
            {item["management_scope_uid"] for item in scopes},
            set(source["scope_uids"]),
        )
        self.assertEqual(
            {item["organization_unit_uid"] for item in scopes},
            set(source["owner_uids"]),
        )

    def test_department_receive_is_idempotent(self):
        self._build_department_task()

        self._use_target()
        initialize_application_database()

        first = receive_survey_task_package(self.package_path)
        second = receive_survey_task_package(self.package_path)

        self.assertFalse(first.already_received)
        self.assertTrue(second.already_received)
        self.assertEqual(
            first.task_workspace_id,
            second.task_workspace_id,
        )

        with database.get_connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS value "
                "FROM survey_task_workspaces"
            ).fetchone()

        self.assertEqual(int(row["value"]), 1)


if __name__ == "__main__":
    unittest.main()
