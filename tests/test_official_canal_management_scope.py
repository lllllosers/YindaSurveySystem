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
from services.canal_management_scope_integrity import (
    check_canal_management_scope_integrity,
)
from services.official_canal_management_scope import (
    OFFICIAL_CANAL_MANAGEMENT_SCOPE_VERSION,
    get_confirmed_official_scope_specs,
    seed_official_canal_management_scopes,
)


class OfficialCanalManagementScopeTestCase(
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
            / "official_scope.db"
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

    def test_fresh_bootstrap_registers_official_scope_seed(
        self,
    ):
        result = (
            initialize_application_database()
        )

        self.assertIn(
            "official_canal_management_scope",
            result,
        )

        scope_result = (
            result[
                "official_canal_management_scope"
            ]
        )

        self.assertTrue(
            scope_result[
                "applied"
            ]
        )

        expected_count = len(
            get_confirmed_official_scope_specs()
        )

        self.assertEqual(
            expected_count,
            63,
        )

        self.assertEqual(
            scope_result[
                "scope_count"
            ],
            expected_count,
        )

        with database.get_connection() as connection:
            seed_row = connection.execute(
                """
                SELECT seed_key
                FROM master_data_seed_history
                WHERE seed_key = ?
                """,
                (
                    OFFICIAL_CANAL_MANAGEMENT_SCOPE_VERSION,
                ),
            ).fetchone()

            scope_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*) AS value
                    FROM canal_management_scopes
                    WHERE master_key IS NOT NULL
                    """
                ).fetchone()[
                    "value"
                ]
            )

        self.assertIsNotNone(
            seed_row
        )

        self.assertEqual(
            scope_count,
            expected_count,
        )

    def test_trunk_canals_are_not_guessed(
        self,
    ):
        initialize_application_database()

        with database.get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    canal.master_key,
                    COUNT(cms.id)
                        AS scope_count
                FROM canal_units
                    AS canal
                LEFT JOIN canal_management_scopes
                    AS cms
                    ON cms.canal_unit_id
                        = canal.id
                WHERE canal.master_key IN (
                    'CANAL-G01',
                    'CANAL-G02',
                    'CANAL-G03',
                    'CANAL-G04',
                    'CANAL-G05'
                )
                GROUP BY canal.id
                ORDER BY canal.master_key
                """
            ).fetchall()

        self.assertEqual(
            len(
                rows
            ),
            5,
        )

        self.assertTrue(
            all(
                int(
                    row[
                        "scope_count"
                    ]
                )
                == 0
                for row in rows
            )
        )

    def test_scope_seed_is_idempotent(
        self,
    ):
        initialize_application_database()

        second = (
            seed_official_canal_management_scopes()
        )

        self.assertFalse(
            second[
                "applied"
            ]
        )

        self.assertTrue(
            second[
                "already_applied"
            ]
        )

    def test_manual_description_is_not_overwritten(
        self,
    ):
        initialize_application_database()

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM canal_management_scopes
                WHERE master_key =
                    'CMS-CANAL-S001-ORG-D01-O03'
                """
            ).fetchone()

            self.assertIsNotNone(
                row
            )

            connection.execute(
                """
                UPDATE canal_management_scopes
                SET description = ?
                WHERE id = ?
                """,
                (
                    "甲方后续补充说明",
                    int(
                        row[
                            "id"
                        ]
                    ),
                ),
            )

        initialize_application_database()

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT description
                FROM canal_management_scopes
                WHERE master_key =
                    'CMS-CANAL-S001-ORG-D01-O03'
                """
            ).fetchone()

        self.assertEqual(
            row[
                "description"
            ],
            "甲方后续补充说明",
        )

    def test_integrity_report_is_clean_on_fresh_database(
        self,
    ):
        initialize_application_database()

        report = (
            check_canal_management_scope_integrity()
        )

        self.assertTrue(
            report.ok
        )

        self.assertEqual(
            report.error_count,
            0,
        )

        self.assertEqual(
            report.scope_count,
            63,
        )

    def test_integrity_detects_missing_official_scope(
        self,
    ):
        initialize_application_database()

        with database.get_connection() as connection:
            connection.execute(
                """
                DELETE FROM canal_management_scopes
                WHERE master_key =
                    'CMS-CANAL-S001-ORG-D01-O03'
                """
            )

        report = (
            check_canal_management_scope_integrity()
        )

        codes = {
            issue.code
            for issue in report.issues
        }

        self.assertIn(
            "OFFICIAL_SCOPE_MISSING",
            codes,
        )


if __name__ == "__main__":
    unittest.main()
