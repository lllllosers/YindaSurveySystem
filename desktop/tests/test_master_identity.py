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
from services.master_identity import (
    deterministic_master_uid,
    synchronize_official_master_identities,
)
from services.official_master_data import (
    seed_official_master_data,
)


class MasterIdentityTestCase(
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
            / "master_identity.db"
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

    def test_deterministic_uid_is_stable(
        self,
    ):
        first = deterministic_master_uid(
            "organization",
            "ORG-D01-O03",
        )

        second = deterministic_master_uid(
            "organization",
            "ORG-D01-O03",
        )

        other = deterministic_master_uid(
            "canal",
            "CANAL-S001",
        )

        self.assertEqual(
            first,
            second,
        )
        self.assertEqual(
            len(first),
            32,
        )
        self.assertNotEqual(
            first,
            other,
        )

    def test_existing_seeded_random_uids_are_migrated(
        self,
    ):
        # 模拟旧版本数据库：
        # 先按旧流程建库/种子，此时官方主数据由 Stage 08
        # 随机 UID 触发器生成。
        database.init_database()
        seed_official_master_data()

        with database.get_connection() as connection:
            before = connection.execute(
                """
                SELECT
                    organization_unit_uid
                FROM organization_units
                WHERE master_key = ?
                """,
                (
                    "ORG-D01-O03",
                ),
            ).fetchone()

        expected = deterministic_master_uid(
            "organization",
            "ORG-D01-O03",
        )

        self.assertNotEqual(
            before[
                "organization_unit_uid"
            ],
            expected,
        )

        result = (
            synchronize_official_master_identities()
        )

        self.assertGreater(
            result[
                "changed_row_count"
            ],
            0,
        )

        with database.get_connection() as connection:
            organization = (
                connection.execute(
                    """
                    SELECT
                        organization_unit_uid
                    FROM organization_units
                    WHERE master_key = ?
                    """,
                    (
                        "ORG-D01-O03",
                    ),
                ).fetchone()
            )

            canal = connection.execute(
                """
                SELECT
                    canal_unit_uid
                FROM canal_units
                WHERE master_key = ?
                """,
                (
                    "CANAL-S001",
                ),
            ).fetchone()

        self.assertEqual(
            organization[
                "organization_unit_uid"
            ],
            expected,
        )

        self.assertEqual(
            canal["canal_unit_uid"],
            deterministic_master_uid(
                "canal",
                "CANAL-S001",
            ),
        )

    def test_sync_is_idempotent(
        self,
    ):
        initialize_application_database()

        first = (
            synchronize_official_master_identities()
        )
        second = (
            synchronize_official_master_identities()
        )

        self.assertEqual(
            first[
                "changed_row_count"
            ],
            0,
        )
        self.assertEqual(
            second[
                "changed_row_count"
            ],
            0,
        )
        self.assertTrue(
            second[
                "already_synchronized"
            ],
        )

    def test_two_independent_databases_get_same_official_uids(
        self,
    ):
        values = []

        for index in (
            1,
            2,
        ):
            database.DATA_DIR = (
                self.temp_root
                / f"local_data_{index}"
            )
            database.DB_PATH = (
                database.DATA_DIR
                / "db.sqlite"
            )

            initialize_application_database()

            with database.get_connection() as connection:
                row = connection.execute(
                    """
                    SELECT
                        organization_unit_uid
                    FROM organization_units
                    WHERE master_key = ?
                    """,
                    (
                        "ORG-D01-O03",
                    ),
                ).fetchone()

                canal = connection.execute(
                    """
                    SELECT
                        canal_unit_uid
                    FROM canal_units
                    WHERE master_key = ?
                    """,
                    (
                        "CANAL-S001",
                    ),
                ).fetchone()

            values.append(
                (
                    row[
                        "organization_unit_uid"
                    ],
                    canal[
                        "canal_unit_uid"
                    ],
                )
            )

        self.assertEqual(
            values[0],
            values[1],
        )


if __name__ == "__main__":
    unittest.main()
