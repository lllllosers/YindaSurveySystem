import gc
import json
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
from services.survey_media import (
    import_survey_media,
)
from services.survey_result_import import (
    import_survey_result_package,
)
from services.survey_result_package import (
    SurveyResultExportRequest,
    export_survey_result_package,
)
from services.survey_result_package_reader import (
    load_survey_result_package,
)


class SurveyResultImportTestCase(
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
            / "child_result.ydresult"
        )

        self._build_source_package()
        self._prepare_target()

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

    def _build_source_package(self):
        self._use_source()
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
                    "2026汇总测试项目",
                    "汇总测试",
                ),
            )
            self.source_project_id = int(
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
                    self.source_project_id,
                    "2026汇总测试批次",
                    "MERGE-2026",
                ),
            )
            self.source_batch_id = int(
                batch.lastrowid
            )

            project_row = connection.execute(
                """
                SELECT project_uid
                FROM projects
                WHERE id = ?
                """,
                (
                    self.source_project_id,
                ),
            ).fetchone()
            self.project_uid = (
                project_row[
                    "project_uid"
                ]
            )

            batch_row = connection.execute(
                """
                SELECT survey_batch_uid
                FROM survey_batches
                WHERE id = ?
                """,
                (
                    self.source_batch_id,
                ),
            ).fetchone()
            self.batch_uid = (
                batch_row[
                    "survey_batch_uid"
                ]
            )

            office = connection.execute(
                """
                SELECT
                    id,
                    parent_id
                FROM organization_units
                WHERE master_key = ?
                """,
                (
                    "ORG-D01-O03",
                ),
            ).fetchone()

            canal = connection.execute(
                """
                SELECT id
                FROM canal_units
                WHERE master_key = ?
                """,
                (
                    "CANAL-S001",
                ),
            ).fetchone()

            self.office_id = int(
                office["id"]
            )
            self.department_id = int(
                office["parent_id"]
            )
            self.canal_id = int(
                canal["id"]
            )

            form = connection.execute(
                """
                SELECT
                    fv.id AS form_version_id,
                    fd.asset_type
                FROM form_definitions AS fd
                JOIN form_versions AS fv
                  ON fv.form_definition_id = fd.id
                WHERE fd.series = 'series_2'
                  AND fd.record_type = 'engineering'
                  AND fd.is_enabled = 1
                  AND fv.is_current = 1
                ORDER BY fd.sort_order, fd.id
                LIMIT 1
                """
            ).fetchone()

            self.form_version_id = int(
                form[
                    "form_version_id"
                ]
            )
            asset_type = str(
                form["asset_type"]
                or "test_asset"
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
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
                """,
                (
                    self.source_project_id,
                    "下级汇总测试工程",
                    asset_type,
                    self.office_id,
                    self.canal_id,
                    "7-77-03-01-001",
                    self.source_batch_id,
                ),
            )
            self.source_asset_id = int(
                asset.lastrowid
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
                    business_code,
                    survey_date,
                    overall_grade,
                    survey_comment,
                    record_status,
                    record_data_json
                )
                VALUES (
                    ?, ?, ?, 'engineering',
                    ?, ?, ?, ?, ?, ?, ?,
                    'completed', ?
                )
                """,
                (
                    self.source_project_id,
                    self.source_batch_id,
                    self.form_version_id,
                    self.office_id,
                    self.canal_id,
                    self.source_asset_id,
                    "7-77-03-01-001",
                    "2026-09-17",
                    "B",
                    "下级成果",
                    json.dumps(
                        {
                            "demo": "child",
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            self.source_record_id = int(
                record.lastrowid
            )

            # 模拟基层电脑已经由 Stage 12.3 自动绑定来源任务。
            connection.execute(
                """
                UPDATE survey_records
                SET
                    source_task_uid = ?,
                    source_management_scope_uid = ?
                WHERE id = ?
                """,
                (
                    "child-task-001",
                    "child-scope-001",
                    self.source_record_id,
                ),
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
                    self.source_record_id,
                    "A01",
                    "主体",
                    "汇总测试分项",
                    "B",
                    "测试描述",
                    "测试备注",
                ),
            )

        media_source = (
            self.temp_root
            / "source_photo.jpg"
        )
        media_source.write_bytes(
            b"stage-12-7-media"
        )

        import_survey_media(
            survey_record_id=(
                self.source_record_id
            ),
            source_file=(
                media_source
            ),
            media_role="overview",
            sequence_no=1,
        )

        export_survey_result_package(
            SurveyResultExportRequest(
                project_id=(
                    self.source_project_id
                ),
                survey_batch_id=(
                    self.source_batch_id
                ),
                survey_record_ids=(
                    self.source_record_id,
                ),
                output_path=(
                    self.package_path
                ),
                result_name=(
                    "下级成果包"
                ),
            )
        )

        self.package_contents = (
            load_survey_result_package(
                self.package_path
            )
        )

    def _prepare_target(self):
        self._use_target()
        initialize_application_database()

        with database.get_connection() as connection:
            project = connection.execute(
                """
                INSERT INTO projects (
                    project_uid,
                    name,
                    short_name,
                    status
                )
                VALUES (?, ?, ?, 'active')
                """,
                (
                    self.project_uid,
                    "2026汇总测试项目",
                    "汇总测试",
                ),
            )
            self.target_project_id = int(
                project.lastrowid
            )

            batch = connection.execute(
                """
                INSERT INTO survey_batches (
                    survey_batch_uid,
                    project_id,
                    batch_name,
                    batch_code,
                    status
                )
                VALUES (?, ?, ?, ?, 'active')
                """,
                (
                    self.batch_uid,
                    self.target_project_id,
                    "2026汇总测试批次",
                    "MERGE-2026",
                ),
            )
            self.target_batch_id = int(
                batch.lastrowid
            )

            office = connection.execute(
                """
                SELECT
                    id,
                    parent_id,
                    organization_unit_uid
                FROM organization_units
                WHERE master_key = ?
                """,
                (
                    "ORG-D01-O03",
                ),
            ).fetchone()

            scope = connection.execute(
                """
                SELECT
                    cms.management_scope_uid,
                    cms.canal_unit_id,
                    cu.canal_unit_uid,
                    ou.organization_unit_uid,
                    cu.name AS canal_name,
                    cu.canal_level,
                    cms.range_mode,
                    cms.start_stake_text,
                    cms.start_stake_value,
                    cms.end_stake_text,
                    cms.end_stake_value,
                    cms.sort_order,
                    cms.status,
                    cms.description
                FROM canal_management_scopes AS cms
                JOIN canal_units AS cu
                  ON cu.id = cms.canal_unit_id
                JOIN organization_units AS ou
                  ON ou.id = cms.organization_unit_id
                WHERE cms.master_key = ?
                """,
                (
                    "CMS-CANAL-S001-ORG-D01-O03",
                ),
            ).fetchone()

            self.assertIsNotNone(
                scope
            )

            # 模拟目标库本身也处在父任务工作区。
            # Stage 14.4.2 起，父任务范围使用冻结 scope snapshot，
            # 不再写入已删除的 测试阶段旧的渠道任务关系表。
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
                    "parent-task-001",
                    "parent-package-001",
                    self.target_project_id,
                    self.target_batch_id,
                    int(
                        office["id"]
                    ),
                    "父级任务",
                    (
                        "task_packages/"
                        "parent-task-001/"
                        "parent-package-001.ydtask"
                    ),
                    "1" * 64,
                ),
            )

            workspace_id = int(
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
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    workspace_id,
                    scope[
                        "management_scope_uid"
                    ],
                    int(
                        scope[
                            "canal_unit_id"
                        ]
                    ),
                    scope[
                        "canal_unit_uid"
                    ],
                    scope[
                        "organization_unit_uid"
                    ],
                    scope[
                        "canal_name"
                    ],
                    scope[
                        "canal_level"
                    ],
                    scope[
                        "range_mode"
                    ],
                    scope[
                        "start_stake_text"
                    ],
                    scope[
                        "start_stake_value"
                    ],
                    scope[
                        "end_stake_text"
                    ],
                    scope[
                        "end_stake_value"
                    ],
                    int(
                        scope[
                            "sort_order"
                        ]
                        or 0
                    ),
                    scope[
                        "status"
                    ],
                    scope[
                        "description"
                    ],
                ),
            )

        self._seed_child_issue_history()

    def _seed_child_issue_history(
        self,
    ):
        from services.survey_task_issue_history import (
            record_issued_survey_task,
        )

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    cu.canal_unit_uid,
                    cu.name AS canal_name,
                    cu.canal_level,
                    ou.organization_unit_uid,
                    ou.name AS organization_name,
                    dept.organization_unit_uid
                        AS department_uid,
                    dept.name AS department_name
                FROM canal_units AS cu
                JOIN organization_units AS ou
                  ON ou.master_key = ?
                JOIN organization_units AS dept
                  ON dept.id = ou.parent_id
                WHERE cu.master_key = ?
                """,
                (
                    "ORG-D01-O03",
                    "CANAL-S001",
                ),
            ).fetchone()

        manifest = {
            "task_uid": "child-task-001",
            "task_schema_version": "2.0",
            "app_version": "0.7.0",
            "project_uid": self.project_uid,
            "survey_batch_uid": self.batch_uid,
        }

        task_document = {
            "task_schema_version": "2.0",
            "task_uid": "child-task-001",
            "task_name": "下级来源任务",
            "notes": None,
            "project": {
                "project_uid": self.project_uid,
                "name": "2026汇总测试项目",
                "short_name": "汇总测试",
            },
            "survey_batch": {
                "survey_batch_uid": self.batch_uid,
                "batch_name": "2026汇总测试批次",
                "batch_code": "MERGE-2026",
                "start_date": None,
                "end_date": None,
            },
            "assignment": {
                "department_uid": row[
                    "department_uid"
                ],
                "department_name": row[
                    "department_name"
                ],
                "organization_unit_uid": row[
                    "organization_unit_uid"
                ],
                "organization_name": row[
                    "organization_name"
                ],
            },
            "scope": {
                "selected_management_scope_uids": [
                    "child-scope-001",
                ],
                "selected_management_scope_count": 1,
            },
            "created_at": "2026-09-18T18:00:00+08:00",
        }

        record_issued_survey_task(
            package_uid="child-issued-package-001",
            manifest=manifest,
            task_document=task_document,
            management_scopes=[
                {
                    "management_scope_uid": "child-scope-001",
                    "canal_uid": row[
                        "canal_unit_uid"
                    ],
                    "organization_unit_uid": row[
                        "organization_unit_uid"
                    ],
                    "range_mode": "segment_unknown",
                    "start_stake_text": None,
                    "start_stake_value": None,
                    "end_stake_text": None,
                    "end_stake_value": None,
                    "sort_order": 1,
                    "status": "active",
                    "description": "下级任务冻结分管段",
                }
            ],
            canal_units=[
                {
                    "canal_uid": row[
                        "canal_unit_uid"
                    ],
                    "name": row[
                        "canal_name"
                    ],
                    "canal_level": row[
                        "canal_level"
                    ],
                }
            ],
        )

    def _fake_backup(self):
        path = (
            self.target_data_dir
            / "backups"
            / "fake_pre_import.db"
        )
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.write_bytes(
            b"fake-backup"
        )
        return path

    @patch(
        "services.survey_result_import."
        "create_database_backup"
    )
    def test_imports_complete_result_transactionally(
        self,
        mock_backup,
    ):
        self._use_target()
        mock_backup.return_value = (
            self._fake_backup()
        )

        result = (
            import_survey_result_package(
                self.package_path
            )
        )

        self.assertFalse(
            result.already_imported
        )
        self.assertEqual(
            result.imported_assets,
            1,
        )
        self.assertEqual(
            result.imported_records,
            1,
        )
        self.assertEqual(
            result.imported_inspections,
            1,
        )
        self.assertEqual(
            result.imported_media,
            1,
        )

        source_record = (
            self.package_contents.survey_records[
                0
            ]
        )
        source_media = (
            self.package_contents.survey_media[
                0
            ]
        )

        with database.get_connection() as connection:
            record = connection.execute(
                """
                SELECT
                    id,
                    source_task_uid,
                    source_management_scope_uid
                FROM survey_records
                WHERE survey_record_uid = ?
                """,
                (
                    source_record[
                        "survey_record_uid"
                    ],
                ),
            ).fetchone()

            self.assertIsNotNone(
                record
            )
            self.assertEqual(
                record[
                    "source_task_uid"
                ],
                "child-task-001",
            )
            self.assertEqual(
                record[
                    "source_management_scope_uid"
                ],
                "child-scope-001",
            )

            media = connection.execute(
                """
                SELECT
                    stored_relative_path,
                    file_sha256
                FROM survey_media
                WHERE media_uid = ?
                """,
                (
                    source_media[
                        "media_uid"
                    ],
                ),
            ).fetchone()

            import_log = connection.execute(
                """
                SELECT COUNT(*) AS count_value
                FROM survey_result_imports
                """
            ).fetchone()

            current_workspace = (
                connection.execute(
                    """
                    SELECT task_uid
                    FROM survey_task_workspaces
                    WHERE is_current = 1
                    """
                ).fetchone()
            )

        self.assertEqual(
            int(
                import_log[
                    "count_value"
                ]
            ),
            1,
        )

        self.assertEqual(
            current_workspace[
                "task_uid"
            ],
            "parent-task-001",
        )

        media_path = (
            database.DATA_DIR
            / media[
                "stored_relative_path"
            ]
        )

        self.assertTrue(
            media_path.exists()
        )
        self.assertEqual(
            media_path.read_bytes(),
            b"stage-12-7-media",
        )

        self.assertTrue(
            result.managed_package_path.exists()
        )

        mock_backup.assert_called_once()

    @patch(
        "services.survey_result_import."
        "create_database_backup"
    )
    def test_second_import_same_package_is_idempotent(
        self,
        mock_backup,
    ):
        self._use_target()
        mock_backup.return_value = (
            self._fake_backup()
        )

        first = (
            import_survey_result_package(
                self.package_path
            )
        )

        second = (
            import_survey_result_package(
                self.package_path
            )
        )

        self.assertFalse(
            first.already_imported
        )
        self.assertTrue(
            second.already_imported
        )

        # 第二次在重复导入日志命中后直接返回，
        # 不再创建额外备份。
        self.assertEqual(
            mock_backup.call_count,
            1,
        )

        with database.get_connection() as connection:
            counts = connection.execute(
                """
                SELECT
                    (
                        SELECT COUNT(*)
                        FROM survey_records
                    ) AS records,
                    (
                        SELECT COUNT(*)
                        FROM survey_result_imports
                    ) AS imports
                """
            ).fetchone()

        self.assertEqual(
            int(
                counts[
                    "records"
                ]
            ),
            1,
        )
        self.assertEqual(
            int(
                counts[
                    "imports"
                ]
            ),
            1,
        )

    @patch(
        "services.survey_result_import."
        "_install_staged_media_file",
        side_effect=RuntimeError(
            "模拟影像安装失败"
        ),
    )
    @patch(
        "services.survey_result_import."
        "create_database_backup"
    )
    def test_file_failure_rolls_back_database(
        self,
        mock_backup,
        mock_install,
    ):
        self._use_target()
        mock_backup.return_value = (
            self._fake_backup()
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "模拟影像安装失败",
        ):
            import_survey_result_package(
                self.package_path
            )

        with database.get_connection() as connection:
            counts = connection.execute(
                """
                SELECT
                    (
                        SELECT COUNT(*)
                        FROM engineering_assets
                    ) AS assets,
                    (
                        SELECT COUNT(*)
                        FROM survey_records
                    ) AS records,
                    (
                        SELECT COUNT(*)
                        FROM inspection_results
                    ) AS inspections,
                    (
                        SELECT COUNT(*)
                        FROM survey_media
                    ) AS media,
                    (
                        SELECT COUNT(*)
                        FROM survey_result_imports
                    ) AS imports
                """
            ).fetchone()

            current_workspace = (
                connection.execute(
                    """
                    SELECT task_uid
                    FROM survey_task_workspaces
                    WHERE is_current = 1
                    """
                ).fetchone()
            )

        self.assertEqual(
            tuple(
                counts
            ),
            (
                0,
                0,
                0,
                0,
                0,
            ),
        )

        self.assertEqual(
            current_workspace[
                "task_uid"
            ],
            "parent-task-001",
        )

        self.assertFalse(
            (
                database.DATA_DIR
                / "result_packages"
            ).exists()
            and any(
                (
                    database.DATA_DIR
                    / "result_packages"
                ).rglob(
                    "*.ydresult"
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
