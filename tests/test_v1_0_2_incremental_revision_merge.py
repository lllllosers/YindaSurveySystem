import gc
import json
import sys
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
from tests.test_survey_result_import import (
    SurveyResultImportTestCase,
)


class V102IncrementalRevisionMergeTestCase(
    unittest.TestCase,
):
    def setUp(self):
        self.base = SurveyResultImportTestCase(
            methodName=(
                "test_imports_complete_result_transactionally"
            )
        )
        self.base.setUp()

    def tearDown(self):
        try:
            self.base.tearDown()
        finally:
            gc.collect()

    def _create_source_record(
        self,
        sequence,
    ):
        base = self.base
        base._use_source()

        code = (
            f"7-77-03-01-{sequence:03d}"
        )

        with database.get_connection() as connection:
            form = connection.execute(
                """
                SELECT
                    fd.asset_type
                FROM form_versions AS fv
                JOIN form_definitions AS fd
                  ON fd.id = fv.form_definition_id
                WHERE fv.id = ?
                """,
                (
                    base.form_version_id,
                ),
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
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
                """,
                (
                    base.source_project_id,
                    f"增量测试工程{sequence}",
                    form["asset_type"] or "test_asset",
                    base.office_id,
                    base.canal_id,
                    code,
                    base.source_batch_id,
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
                    survey_comment,
                    record_status,
                    record_data_json
                )
                VALUES (
                    ?, ?, ?, ?, ?, 'engineering',
                    ?, ?, ?, ?, ?, ?, ?,
                    'completed', ?
                )
                """,
                (
                    "child-task-001",
                    "child-scope-001",
                    base.source_project_id,
                    base.source_batch_id,
                    base.form_version_id,
                    base.office_id,
                    base.canal_id,
                    asset_id,
                    code,
                    "2026-09-20",
                    "B",
                    f"增量记录{sequence}",
                    json.dumps(
                        {
                            "sequence": sequence,
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
                    "A01",
                    "主体",
                    "增量测试分项",
                    "B",
                    f"描述{sequence}",
                    None,
                ),
            )

        return record_id

    def _export_source(
        self,
        record_ids,
        filename,
    ):
        base = self.base
        base._use_source()

        path = (
            base.temp_root
            / filename
        )

        export_survey_result_package(
            SurveyResultExportRequest(
                project_id=(
                    base.source_project_id
                ),
                survey_batch_id=(
                    base.source_batch_id
                ),
                survey_record_ids=tuple(
                    record_ids
                ),
                output_path=path,
                result_name=filename,
            )
        )

        return path

    def _revise_source_record(
        self,
        comment,
    ):
        base = self.base
        base._use_source()

        with database.get_connection() as connection:
            connection.execute(
                """
                UPDATE survey_records
                SET
                    survey_comment = ?,
                    record_data_json = ?,
                    revision_no = revision_no + 1,
                    updated_at = datetime(
                        'now',
                        'localtime'
                    )
                WHERE id = ?
                """,
                (
                    comment,
                    json.dumps(
                        {
                            "demo": comment,
                        },
                        ensure_ascii=False,
                    ),
                    base.source_record_id,
                ),
            )

    def test_three_existing_plus_two_new_is_incremental(self):
        base = self.base

        second = self._create_source_record(2)
        third = self._create_source_record(3)

        first_package = self._export_source(
            (
                base.source_record_id,
                second,
                third,
            ),
            "day1_three.ydresult",
        )

        base._use_target()
        day1 = import_survey_result_package(
            first_package
        )
        self.assertEqual(
            day1.imported_records,
            3,
        )

        fourth = self._create_source_record(4)
        fifth = self._create_source_record(5)

        second_package = self._export_source(
            (
                base.source_record_id,
                second,
                third,
                fourth,
                fifth,
            ),
            "day2_five.ydresult",
        )

        base._use_target()
        report = preflight_survey_result_import(
            second_package
        )

        self.assertTrue(
            report.can_import,
            report.format_text(),
        )
        self.assertEqual(
            report.existing_records,
            3,
        )
        self.assertEqual(
            report.new_records,
            2,
        )
        self.assertEqual(
            report.updated_records,
            0,
        )
        self.assertTrue(
            report.has_importable_changes
        )

        day2 = import_survey_result_package(
            second_package
        )

        self.assertEqual(
            day2.imported_records,
            2,
        )
        self.assertEqual(
            day2.existing_records,
            3,
        )

        with database.get_connection() as connection:
            total = int(
                connection.execute(
                    """
                    SELECT COUNT(*) AS value
                    FROM survey_records
                    WHERE project_id = ?
                      AND survey_batch_id = ?
                    """,
                    (
                        base.target_project_id,
                        base.target_batch_id,
                    ),
                ).fetchone()[
                    "value"
                ]
            )

        self.assertEqual(
            total,
            5,
        )

    def test_child_correction_requires_confirmation_then_updates(self):
        base = self.base
        base._use_target()

        import_survey_result_package(
            base.package_path
        )

        self._revise_source_record(
            "下级发现错录后更正"
        )
        corrected = self._export_source(
            (
                base.source_record_id,
            ),
            "corrected_v2.ydresult",
        )

        base._use_target()
        report = preflight_survey_result_import(
            corrected
        )

        self.assertTrue(
            report.can_import,
            report.format_text(),
        )
        self.assertEqual(
            report.updated_records,
            1,
        )
        self.assertTrue(
            report.has_updates
        )
        self.assertIn(
            "待更新 1",
            report.format_text(),
        )

        with self.assertRaises(ValueError):
            import_survey_result_package(
                corrected
            )

        result = import_survey_result_package(
            corrected,
            accept_updates=True,
        )

        self.assertEqual(
            result.updated_records,
            1,
        )

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    survey_comment,
                    revision_no,
                    source_revision_no
                FROM survey_records
                WHERE survey_record_uid = ?
                """,
                (
                    base.package_contents
                    .survey_records[0][
                        "survey_record_uid"
                    ],
                ),
            ).fetchone()

        self.assertEqual(
            row["survey_comment"],
            "下级发现错录后更正",
        )
        self.assertEqual(
            (
                int(row["revision_no"]),
                int(row["source_revision_no"]),
            ),
            (
                2,
                2,
            ),
        )

    def test_both_sides_modified_is_blocking_conflict(self):
        base = self.base
        base._use_target()

        import_survey_result_package(
            base.package_path
        )

        record_uid = (
            base.package_contents
            .survey_records[0][
                "survey_record_uid"
            ]
        )

        # 上级在最近一次下级版本之后做了本地修改。
        with database.get_connection() as connection:
            connection.execute(
                """
                UPDATE survey_records
                SET
                    survey_comment = ?,
                    revision_no = revision_no + 1
                WHERE survey_record_uid = ?
                """,
                (
                    "上级本地修改",
                    record_uid,
                ),
            )

        # 下级也从同一个来源版本继续修改。
        self._revise_source_record(
            "下级同时修改"
        )
        child_v2 = self._export_source(
            (
                base.source_record_id,
            ),
            "child_diverged_v2.ydresult",
        )

        base._use_target()
        report = preflight_survey_result_import(
            child_v2
        )

        self.assertFalse(
            report.can_import
        )
        self.assertEqual(
            report.conflict_records,
            1,
        )
        self.assertTrue(
            any(
                issue.code
                == "RECORD_DIVERGED"
                for issue in report.issues
            )
        )

    def test_stale_result_never_rolls_back_newer_source_version(self):
        base = self.base
        base._use_target()

        import_survey_result_package(
            base.package_path
        )

        self._revise_source_record(
            "下级第二版"
        )
        child_v2 = self._export_source(
            (
                base.source_record_id,
            ),
            "child_v2.ydresult",
        )

        base._use_target()
        import_survey_result_package(
            child_v2,
            accept_updates=True,
        )

        stale = preflight_survey_result_import(
            base.package_path
        )

        self.assertTrue(
            stale.can_import,
            stale.format_text(),
        )
        self.assertEqual(
            stale.stale_records,
            1,
        )
        self.assertFalse(
            stale.has_importable_changes
        )

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    survey_comment,
                    source_revision_no
                FROM survey_records
                WHERE survey_record_uid = ?
                """,
                (
                    base.package_contents
                    .survey_records[0][
                        "survey_record_uid"
                    ],
                ),
            ).fetchone()

        self.assertEqual(
            row["survey_comment"],
            "下级第二版",
        )
        self.assertEqual(
            int(row["source_revision_no"]),
            2,
        )


if __name__ == "__main__":
    unittest.main()
