import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from services.survey_scope import (
    SurveyScope,
    filter_records_by_scope,
    resolve_descendant_ids,
    resolve_survey_scope,
)


class SurveyScopeTestCase(
    unittest.TestCase,
):
    def setUp(self):
        self.organization_rows = [
            {
                "id": 1,
                "parent_id": None,
            },
            {
                "id": 2,
                "parent_id": 1,
            },
            {
                "id": 3,
                "parent_id": 1,
            },
            {
                "id": 4,
                "parent_id": 2,
            },
        ]

        self.canal_rows = [
            {
                "id": 10,
                "parent_id": None,
            },
            {
                "id": 11,
                "parent_id": 10,
            },
            {
                "id": 12,
                "parent_id": 11,
            },
            {
                "id": 13,
                "parent_id": 10,
            },
        ]

    def test_scope_normalizes_and_deduplicates(
        self,
    ):
        scope = SurveyScope(
            project_id="1",
            survey_batch_id="2",
            organization_unit_ids=(
                3,
                "3",
                2,
            ),
            canal_unit_ids=(
                "10",
                10,
            ),
            form_codes=(
                "form_2_1",
                "",
                "form_2_1",
                "form_2_2",
            ),
            record_statuses=(
                "completed",
                "completed",
            ),
        )

        self.assertEqual(
            scope.project_id,
            1,
        )
        self.assertEqual(
            scope.survey_batch_id,
            2,
        )
        self.assertEqual(
            scope.organization_unit_ids,
            (3, 2),
        )
        self.assertEqual(
            scope.canal_unit_ids,
            (10,),
        )
        self.assertEqual(
            scope.form_codes,
            (
                "form_2_1",
                "form_2_2",
            ),
        )
        self.assertEqual(
            scope.record_statuses,
            ("completed",),
        )

    def test_official_scope_defaults_to_completed(
        self,
    ):
        scope = SurveyScope(
            project_id=1,
            survey_batch_id=2,
        )

        self.assertEqual(
            scope.record_statuses,
            ("completed",),
        )

    def test_resolve_descendants_includes_root(
        self,
    ):
        resolved = resolve_descendant_ids(
            self.organization_rows,
            (2,),
        )

        self.assertEqual(
            resolved,
            frozenset(
                {
                    2,
                    4,
                }
            ),
        )

    def test_resolve_can_disable_descendants(
        self,
    ):
        resolved = resolve_descendant_ids(
            self.canal_rows,
            (10,),
            include_descendants=False,
        )

        self.assertEqual(
            resolved,
            frozenset({10}),
        )

    def test_missing_scope_root_fails_fast(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "基础资料节点不存在",
        ):
            resolve_descendant_ids(
                self.canal_rows,
                (999,),
            )

    def test_empty_dimension_means_no_restriction(
        self,
    ):
        scope = SurveyScope(
            project_id=1,
            survey_batch_id=2,
        )

        resolved = resolve_survey_scope(
            scope,
            organization_rows=(
                self.organization_rows
            ),
            canal_rows=self.canal_rows,
        )

        self.assertIsNone(
            resolved.organization_unit_ids
        )
        self.assertIsNone(
            resolved.canal_unit_ids
        )

    def test_filter_records_uses_all_scope_dimensions(
        self,
    ):
        scope = SurveyScope(
            project_id=1,
            survey_batch_id=2,
            organization_unit_ids=(1,),
            canal_unit_ids=(10,),
            form_codes=("form_2_2",),
        )

        resolved = resolve_survey_scope(
            scope,
            organization_rows=(
                self.organization_rows
            ),
            canal_rows=self.canal_rows,
        )

        records = [
            {
                "name": "match",
                "project_id": 1,
                "survey_batch_id": 2,
                "organization_unit_id": 2,
                "canal_unit_id": 12,
                "form_code": "form_2_2",
                "record_status": (
                    "completed"
                ),
            },
            {
                "name": "draft",
                "project_id": 1,
                "survey_batch_id": 2,
                "organization_unit_id": 2,
                "canal_unit_id": 12,
                "form_code": "form_2_2",
                "record_status": "draft",
            },
            {
                "name": "wrong_form",
                "project_id": 1,
                "survey_batch_id": 2,
                "organization_unit_id": 2,
                "canal_unit_id": 12,
                "form_code": "form_2_3",
                "record_status": (
                    "completed"
                ),
            },
            {
                "name": "wrong_canal",
                "project_id": 1,
                "survey_batch_id": 2,
                "organization_unit_id": 2,
                "canal_unit_id": 99,
                "form_code": "form_2_2",
                "record_status": (
                    "completed"
                ),
            },
        ]

        filtered = (
            filter_records_by_scope(
                records,
                resolved,
            )
        )

        self.assertEqual(
            tuple(
                record["name"]
                for record in filtered
            ),
            ("match",),
        )

    def test_invalid_status_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "调查记录状态无效",
        ):
            SurveyScope(
                project_id=1,
                survey_batch_id=2,
                record_statuses=(
                    "finished",
                ),
            )


if __name__ == "__main__":
    unittest.main()
