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
from services.engineering_numbering_finalization import (
    finalize_engineering_business_codes,
    preview_engineering_numbering_finalization,
)


class V102EngineeringNumberingFinalizationTestCase(
    unittest.TestCase,
):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_directory.name)

        self.original_data_dir = database.DATA_DIR
        self.original_db_path = database.DB_PATH

        database.DATA_DIR = self.temp_root / "local_data"
        database.DB_PATH = (
            database.DATA_DIR / "numbering_finalization.db"
        )

        initialize_application_database()

        project = database.create_project(
            name="正式锁号测试项目",
            short_name="锁号测试",
        )
        self.project_id = int(project["project_id"])

        batch = database.create_survey_batch(
            project_id=self.project_id,
            batch_name="正式锁号测试批次",
            batch_code="FINALIZE-102",
        )
        self.batch_id = int(batch["batch_id"])

        with database.get_connection() as connection:
            office = connection.execute(
                """
                SELECT office.id
                FROM organization_units AS office
                JOIN organization_units AS department
                  ON department.id = office.parent_id
                WHERE office.unit_type = 'water_office'
                  AND office.status = 'active'
                  AND office.business_code IS NOT NULL
                  AND department.business_code IS NOT NULL
                ORDER BY office.id
                LIMIT 1
                """
            ).fetchone()

            canal = connection.execute(
                """
                SELECT id
                FROM canal_units
                WHERE status = 'active'
                  AND canal_level IN ('01', '02', '03', '04')
                ORDER BY id
                LIMIT 1
                """
            ).fetchone()

            point_form = connection.execute(
                """
                SELECT
                    fv.id AS form_version_id,
                    fd.asset_type
                FROM form_definitions AS fd
                JOIN form_versions AS fv
                  ON fv.form_definition_id = fd.id
                WHERE fd.form_code = 'form_2_2'
                  AND fv.is_current = 1
                ORDER BY fv.id DESC
                LIMIT 1
                """
            ).fetchone()

            lined_form = connection.execute(
                """
                SELECT
                    fv.id AS form_version_id,
                    fd.asset_type
                FROM form_definitions AS fd
                JOIN form_versions AS fv
                  ON fv.form_definition_id = fd.id
                WHERE fd.form_code = 'form_2_1'
                  AND fv.is_current = 1
                ORDER BY fv.id DESC
                LIMIT 1
                """
            ).fetchone()

        self.assertIsNotNone(office)
        self.assertIsNotNone(canal)
        self.assertIsNotNone(point_form)
        self.assertIsNotNone(lined_form)

        self.office_id = int(office["id"])
        self.canal_id = int(canal["id"])
        self.point_form_id = int(point_form["form_version_id"])
        self.point_asset_type = point_form["asset_type"]
        self.lined_form_id = int(lined_form["form_version_id"])
        self.lined_asset_type = lined_form["asset_type"]

    def tearDown(self):
        database.DATA_DIR = self.original_data_dir
        database.DB_PATH = self.original_db_path
        gc.collect()
        self.temp_directory.cleanup()

    def _add_point(
        self,
        *,
        stake,
        sequence,
        status="completed",
        revision_no=1,
        name=None,
    ):
        code = f"9-99-03-02-{sequence:03d}"

        with database.get_connection() as connection:
            asset_cursor = connection.execute(
                """
                INSERT INTO engineering_assets (
                    project_id,
                    asset_name,
                    asset_type,
                    organization_unit_id,
                    canal_unit_id,
                    business_code,
                    single_stake_text,
                    single_stake_value,
                    first_survey_batch_id,
                    status,
                    revision_no,
                    source_revision_no,
                    code_status
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    'active', ?, 0, 'provisional'
                )
                """,
                (
                    self.project_id,
                    name or f"点工程{stake}",
                    self.point_asset_type,
                    self.office_id,
                    self.canal_id,
                    code,
                    f"CH{int(stake // 1000)}+{int(stake % 1000):03d}",
                    float(stake),
                    self.batch_id,
                    revision_no,
                ),
            )
            asset_id = int(asset_cursor.lastrowid)

            connection.execute(
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
                    record_status,
                    record_data_json,
                    revision_no,
                    source_revision_no
                )
                VALUES (
                    ?, ?, ?, 'engineering',
                    ?, ?, ?, ?, ?, '{}', ?, 0
                )
                """,
                (
                    self.project_id,
                    self.batch_id,
                    self.point_form_id,
                    self.office_id,
                    self.canal_id,
                    asset_id,
                    code,
                    status,
                    revision_no,
                ),
            )

            return asset_id

    def _add_lined(
        self,
        *,
        start,
        end,
        sequence,
        status="completed",
    ):
        code = f"9-99-03-01-{sequence:03d}"

        with database.get_connection() as connection:
            asset_cursor = connection.execute(
                """
                INSERT INTO engineering_assets (
                    project_id,
                    asset_name,
                    asset_type,
                    organization_unit_id,
                    canal_unit_id,
                    business_code,
                    start_stake_text,
                    start_stake_value,
                    end_stake_text,
                    end_stake_value,
                    first_survey_batch_id,
                    status,
                    code_status
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, 'active', 'provisional'
                )
                """,
                (
                    self.project_id,
                    f"渠段{start}-{end}",
                    self.lined_asset_type,
                    self.office_id,
                    self.canal_id,
                    code,
                    f"CH{int(start // 1000)}+{int(start % 1000):03d}",
                    float(start),
                    f"CH{int(end // 1000)}+{int(end % 1000):03d}",
                    float(end),
                    self.batch_id,
                ),
            )
            asset_id = int(asset_cursor.lastrowid)

            connection.execute(
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
                    record_status,
                    record_data_json
                )
                VALUES (
                    ?, ?, ?, 'engineering',
                    ?, ?, ?, ?, ?, '{}'
                )
                """,
                (
                    self.project_id,
                    self.batch_id,
                    self.lined_form_id,
                    self.office_id,
                    self.canal_id,
                    asset_id,
                    code,
                    status,
                ),
            )

            return asset_id

    def test_finalize_resorts_locks_and_keeps_revision(self):
        upstream_id = self._add_point(
            stake=100.0,
            sequence=9,
            revision_no=7,
            name="上游",
        )
        downstream_id = self._add_point(
            stake=300.0,
            sequence=1,
            revision_no=11,
            name="下游",
        )

        preview = preview_engineering_numbering_finalization(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
        )

        self.assertTrue(
            preview.can_finalize,
            preview.format_text(),
        )
        self.assertFalse(preview.has_warnings)

        result = finalize_engineering_business_codes(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
        )

        self.assertEqual(result.finalized_count, 2)

        with database.get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    ea.id,
                    ea.business_code,
                    ea.code_status,
                    ea.revision_no,
                    sr.business_code AS record_business_code
                FROM engineering_assets AS ea
                JOIN survey_records AS sr
                  ON sr.engineering_asset_id = ea.id
                WHERE ea.id IN (?, ?)
                ORDER BY ea.single_stake_value
                """,
                (
                    upstream_id,
                    downstream_id,
                ),
            ).fetchall()

        self.assertEqual(
            [
                row["business_code"].split("-")[-1]
                for row in rows
            ],
            ["001", "002"],
        )
        self.assertEqual(
            [int(row["revision_no"]) for row in rows],
            [7, 11],
        )

        for row in rows:
            self.assertEqual(row["code_status"], "final")
            self.assertEqual(
                row["business_code"],
                row["record_business_code"],
            )

        second = finalize_engineering_business_codes(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
        )
        self.assertEqual(second.changed_code_count, 0)

    def test_draft_record_blocks_finalization(self):
        self._add_point(
            stake=100.0,
            sequence=1,
            status="draft",
        )

        preview = preview_engineering_numbering_finalization(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
        )

        self.assertFalse(preview.can_finalize)
        self.assertTrue(
            any(
                issue.code == "RECORD_NOT_COMPLETED"
                for issue in preview.errors
            )
        )

    def test_lined_overlap_blocks_finalization(self):
        self._add_lined(
            start=0.0,
            end=1000.0,
            sequence=1,
        )
        self._add_lined(
            start=900.0,
            end=1800.0,
            sequence=2,
        )

        preview = preview_engineering_numbering_finalization(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
        )

        self.assertFalse(preview.can_finalize)
        self.assertTrue(
            any(
                issue.code == "LINED_SECTION_OVERLAP"
                for issue in preview.errors
            )
        )

    def test_lined_gap_warns_and_requires_confirmation(self):
        first_id = self._add_lined(
            start=0.0,
            end=1000.0,
            sequence=8,
        )
        second_id = self._add_lined(
            start=1200.0,
            end=2000.0,
            sequence=9,
        )

        preview = preview_engineering_numbering_finalization(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
        )

        self.assertTrue(
            preview.can_finalize,
            preview.format_text(),
        )
        self.assertTrue(preview.has_warnings)
        self.assertTrue(
            any(
                issue.code == "LINED_SECTION_GAP"
                for issue in preview.warnings
            )
        )

        with self.assertRaises(ValueError):
            finalize_engineering_business_codes(
                project_id=self.project_id,
                survey_batch_id=self.batch_id,
                accept_warnings=False,
            )

        result = finalize_engineering_business_codes(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
            accept_warnings=True,
        )

        self.assertEqual(result.finalized_count, 2)

        with database.get_connection() as connection:
            statuses = [
                row["code_status"]
                for row in connection.execute(
                    """
                    SELECT code_status
                    FROM engineering_assets
                    WHERE id IN (?, ?)
                    ORDER BY id
                    """,
                    (
                        first_id,
                        second_id,
                    ),
                ).fetchall()
            ]

        self.assertEqual(statuses, ["final", "final"])

    def test_lined_section_over_3km_is_warning(self):
        self._add_lined(
            start=0.0,
            end=3500.0,
            sequence=1,
        )

        preview = preview_engineering_numbering_finalization(
            project_id=self.project_id,
            survey_batch_id=self.batch_id,
        )

        self.assertTrue(
            preview.can_finalize,
            preview.format_text(),
        )
        self.assertTrue(
            any(
                issue.code == "LINED_SECTION_OVER_3KM"
                for issue in preview.warnings
            )
        )


if __name__ == "__main__":
    unittest.main()
