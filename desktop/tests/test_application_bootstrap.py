import gc
import shutil
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
from services.official_master_data import (
    OFFICIAL_MASTER_DATA_VERSION,
)


class ApplicationBootstrapTestCase(
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
            / "yinda_survey.db"
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

    def _counts(self):
        with database.get_connection() as connection:
            return {
                "organization_units": int(
                    connection.execute(
                        """
                        SELECT COUNT(*) AS value
                        FROM organization_units
                        WHERE master_key IS NOT NULL
                        """
                    ).fetchone()["value"]
                ),
                "canal_units": int(
                    connection.execute(
                        """
                        SELECT COUNT(*) AS value
                        FROM canal_units
                        WHERE master_key IS NOT NULL
                        """
                    ).fetchone()["value"]
                ),
                "projects": int(
                    connection.execute(
                        """
                        SELECT COUNT(*) AS value
                        FROM projects
                        """
                    ).fetchone()["value"]
                ),
                "survey_batches": int(
                    connection.execute(
                        """
                        SELECT COUNT(*) AS value
                        FROM survey_batches
                        """
                    ).fetchone()["value"]
                ),
                "engineering_assets": int(
                    connection.execute(
                        """
                        SELECT COUNT(*) AS value
                        FROM engineering_assets
                        """
                    ).fetchone()["value"]
                ),
                "survey_records": int(
                    connection.execute(
                        """
                        SELECT COUNT(*) AS value
                        FROM survey_records
                        """
                    ).fetchone()["value"]
                ),
                "form_definitions": int(
                    connection.execute(
                        """
                        SELECT COUNT(*) AS value
                        FROM form_definitions
                        """
                    ).fetchone()["value"]
                ),
            }

    def test_fresh_bootstrap_creates_clean_production_baseline(
        self,
    ):
        result = (
            initialize_application_database()
        )

        self.assertTrue(
            database.DB_PATH.exists()
        )

        self.assertTrue(
            result[
                "official_master_data"
            ]["applied"]
        )

        counts = self._counts()

        self.assertEqual(
            counts["organization_units"],
            25,
        )
        self.assertEqual(
            counts["canal_units"],
            68,
        )

        self.assertEqual(
            counts["projects"],
            0,
        )
        self.assertEqual(
            counts["survey_batches"],
            0,
        )
        self.assertEqual(
            counts["engineering_assets"],
            0,
        )
        self.assertEqual(
            counts["survey_records"],
            0,
        )

        self.assertGreater(
            counts["form_definitions"],
            0,
        )

        with database.get_connection() as connection:
            seed_row = connection.execute(
                """
                SELECT seed_key
                FROM master_data_seed_history
                WHERE seed_key = ?
                """,
                (
                    OFFICIAL_MASTER_DATA_VERSION,
                ),
            ).fetchone()

        self.assertIsNotNone(
            seed_row
        )

    def test_second_bootstrap_does_not_overwrite_manual_changes(
        self,
    ):
        initialize_application_database()

        with database.get_connection() as connection:
            connection.execute(
                """
                UPDATE canal_units
                SET
                    name = ?,
                    description = ?
                WHERE master_key = ?
                """,
                (
                    "总干渠（甲方修改）",
                    "甲方后续补充备注",
                    "CANAL-G01",
                ),
            )

        result = (
            initialize_application_database()
        )

        self.assertFalse(
            result[
                "official_master_data"
            ]["applied"]
        )
        self.assertTrue(
            result[
                "official_master_data"
            ]["already_applied"]
        )

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    name,
                    description
                FROM canal_units
                WHERE master_key = ?
                """,
                ("CANAL-G01",),
            ).fetchone()

        self.assertEqual(
            row["name"],
            "总干渠（甲方修改）",
        )
        self.assertEqual(
            row["description"],
            "甲方后续补充备注",
        )

    def test_deleting_local_data_recreates_official_baseline(
        self,
    ):
        initialize_application_database()

        # 先制造测试业务数据，模拟开发阶段数据库。
        with database.get_connection() as connection:
            connection.execute(
                """
                INSERT INTO projects (
                    name,
                    status
                )
                VALUES (?, ?)
                """,
                (
                    "应被清理的测试项目",
                    "active",
                ),
            )

        self.assertEqual(
            self._counts()["projects"],
            1,
        )

        gc.collect()

        shutil.rmtree(
            database.DATA_DIR
        )

        self.assertFalse(
            database.DATA_DIR.exists()
        )

        result = (
            initialize_application_database()
        )

        self.assertTrue(
            result[
                "official_master_data"
            ]["applied"]
        )

        counts = self._counts()

        self.assertEqual(
            counts["organization_units"],
            25,
        )
        self.assertEqual(
            counts["canal_units"],
            68,
        )
        self.assertEqual(
            counts["projects"],
            0,
        )
        self.assertEqual(
            counts["engineering_assets"],
            0,
        )
        self.assertEqual(
            counts["survey_records"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
