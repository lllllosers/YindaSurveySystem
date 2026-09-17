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
from services.master_data_integrity import (
    check_master_data_integrity,
)


class MasterDataIntegrityTestCase(
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
            / "integrity.db"
        )

        initialize_application_database()

    def tearDown(self):
        gc.collect()

        database.DATA_DIR = (
            self.original_data_dir
        )
        database.DB_PATH = (
            self.original_db_path
        )

        self.temp_directory.cleanup()

    def test_clean_official_master_data_passes(
        self,
    ):
        report = (
            check_master_data_integrity()
        )

        self.assertTrue(
            report.passed
        )
        self.assertEqual(
            report.error_count,
            0,
        )
        self.assertEqual(
            report.organization_count,
            25,
        )
        self.assertEqual(
            report.department_count,
            5,
        )
        self.assertEqual(
            report.office_count,
            20,
        )
        self.assertEqual(
            report.canal_count,
            68,
        )
        self.assertEqual(
            report.canal_level_counts,
            {
                "01": 3,
                "02": 2,
                "03": 47,
                "04": 16,
            },
        )

        # 当前确认口径下，5 条骨干渠管理单位允许为空。
        info_codes = [
            issue.code
            for issue in report.issues
            if issue.severity == "info"
        ]

        self.assertEqual(
            info_codes.count(
                "TRUNK_MANAGEMENT_BLANK"
            ),
            5,
        )

    def test_missing_branch_management_is_error(
        self,
    ):
        with database.get_connection() as connection:
            connection.execute(
                """
                UPDATE canal_units
                SET organization_unit_id = NULL
                WHERE master_key = ?
                """,
                ("CANAL-S001",),
            )

        report = (
            check_master_data_integrity()
        )

        codes = {
            issue.code
            for issue in report.issues
            if issue.severity == "error"
        }

        self.assertIn(
            "CANAL_MANAGEMENT_MISSING",
            codes,
        )
        self.assertFalse(
            report.passed
        )

    def test_invalid_branch_parent_is_error(
        self,
    ):
        with database.get_connection() as connection:
            root = connection.execute(
                """
                SELECT id
                FROM canal_units
                WHERE master_key = ?
                """,
                ("CANAL-G01",),
            ).fetchone()

            connection.execute(
                """
                UPDATE canal_units
                SET parent_id = ?
                WHERE master_key = ?
                """,
                (
                    int(root["id"]),
                    "CANAL-S005",
                ),
            )

        report = (
            check_master_data_integrity()
        )

        codes = {
            issue.code
            for issue in report.issues
            if issue.severity == "error"
        }

        self.assertIn(
            "BRANCH_PARENT_INVALID",
            codes,
        )

    def test_duplicate_office_code_is_error(
        self,
    ):
        with database.get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id
                FROM organization_units
                WHERE parent_id = (
                    SELECT id
                    FROM organization_units
                    WHERE master_key = ?
                )
                AND unit_type = 'water_office'
                ORDER BY id
                LIMIT 2
                """,
                ("ORG-D01",),
            ).fetchall()

            self.assertEqual(
                len(rows),
                2,
            )

            first_code = connection.execute(
                """
                SELECT business_code
                FROM organization_units
                WHERE id = ?
                """,
                (
                    int(rows[0]["id"]),
                ),
            ).fetchone()[
                "business_code"
            ]

            connection.execute(
                """
                UPDATE organization_units
                SET business_code = ?
                WHERE id = ?
                """,
                (
                    first_code,
                    int(rows[1]["id"]),
                ),
            )

        report = (
            check_master_data_integrity()
        )

        codes = {
            issue.code
            for issue in report.issues
            if issue.severity == "error"
        }

        self.assertIn(
            "OFFICE_CODE_DUPLICATE",
            codes,
        )

    def test_duplicate_canal_sort_is_error(
        self,
    ):
        with database.get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, sort_order
                FROM canal_units
                WHERE master_key IS NOT NULL
                ORDER BY id
                LIMIT 2
                """
            ).fetchall()

            connection.execute(
                """
                UPDATE canal_units
                SET sort_order = ?
                WHERE id = ?
                """,
                (
                    int(
                        rows[0][
                            "sort_order"
                        ]
                    ),
                    int(rows[1]["id"]),
                ),
            )

        report = (
            check_master_data_integrity()
        )

        codes = {
            issue.code
            for issue in report.issues
            if issue.severity == "error"
        }

        self.assertIn(
            "CANAL_SORT_DUPLICATE",
            codes,
        )


if __name__ == "__main__":
    unittest.main()
