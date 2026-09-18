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

from services.official_master_data import (
    OFFICIAL_MASTER_DATA_VERSION,
    seed_official_master_data,
)


class OfficialMasterDataTestCase(
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
            / "master_data.db"
        )

        database.init_database()

    def tearDown(self):
        gc.collect()

        database.DATA_DIR = (
            self.original_data_dir
        )
        database.DB_PATH = (
            self.original_db_path
        )

        self.temp_directory.cleanup()

    def test_fresh_seed_creates_official_counts(
        self,
    ):
        result = (
            seed_official_master_data()
        )

        self.assertTrue(
            result["applied"]
        )

        with database.get_connection() as connection:
            organization_count = (
                connection.execute(
                    """
                    SELECT COUNT(*) AS value
                    FROM organization_units
                    WHERE master_key IS NOT NULL
                    """
                ).fetchone()["value"]
            )

            canal_count = (
                connection.execute(
                    """
                    SELECT COUNT(*) AS value
                    FROM canal_units
                    WHERE master_key IS NOT NULL
                    """
                ).fetchone()["value"]
            )

            level_counts = {
                row["canal_level"]:
                int(row["value"])
                for row in (
                    connection.execute(
                        """
                        SELECT
                            canal_level,
                            COUNT(*) AS value
                        FROM canal_units
                        WHERE master_key IS NOT NULL
                        GROUP BY canal_level
                        """
                    ).fetchall()
                )
            }

        self.assertEqual(
            organization_count,
            25,
        )
        self.assertEqual(
            canal_count,
            68,
        )
        self.assertEqual(
            level_counts,
            {
                "01": 3,
                "02": 2,
                "03": 47,
                "04": 16,
            },
        )

    def test_new_table_names_are_authoritative(
        self,
    ):
        seed_official_master_data()

        with database.get_connection() as connection:
            names = {
                row["name"]
                for row in (
                    connection.execute(
                        """
                        SELECT name
                        FROM organization_units
                        WHERE master_key IS NOT NULL
                        """
                    ).fetchall()
                )
            }

        self.assertIn(
            "古山电力提灌所",
            names,
        )
        self.assertIn(
            "尖山庙水库管理所",
            names,
        )
        self.assertIn(
            "石门沟水库管理所",
            names,
        )

        self.assertNotIn(
            "古山电灌水管所",
            names,
        )
        self.assertNotIn(
            "尖山庙水管所",
            names,
        )
        self.assertNotIn(
            "石门沟水管所",
            names,
        )

    def test_major_canals_have_blank_management(
        self,
    ):
        seed_official_master_data()

        with database.get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    master_key,
                    organization_unit_id
                FROM canal_units
                WHERE master_key IN (
                    'CANAL-G01',
                    'CANAL-G02',
                    'CANAL-G03',
                    'CANAL-G04',
                    'CANAL-G05'
                )
                ORDER BY master_key
                """
            ).fetchall()

        self.assertEqual(
            len(rows),
            5,
        )

        self.assertTrue(
            all(
                row["organization_unit_id"]
                is None
                for row in rows
            )
        )

    def test_hierarchy_and_source_column_level_are_preserved(
        self,
    ):
        seed_official_master_data()

        with database.get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    c.master_key,
                    c.name,
                    c.canal_level,
                    p.master_key
                        AS parent_master_key
                FROM canal_units c
                LEFT JOIN canal_units p
                  ON p.id = c.parent_id
                WHERE c.master_key IN (
                    'CANAL-S005',
                    'CANAL-S016',
                    'CANAL-S038',
                    'CANAL-S051',
                    'CANAL-S058'
                )
                ORDER BY c.master_key
                """
            ).fetchall()

        data = {
            row["master_key"]: dict(row)
            for row in rows
        }

        self.assertEqual(
            data["CANAL-S005"][
                "parent_master_key"
            ],
            "CANAL-S004",
        )

        self.assertEqual(
            data["CANAL-S051"][
                "parent_master_key"
            ],
            "CANAL-S050",
        )

        # 这三个名字容易被字面含义误判。
        # 正式层级严格按甲方新表所在列。
        self.assertEqual(
            data["CANAL-S016"][
                "canal_level"
            ],
            "03",
        )
        self.assertEqual(
            data["CANAL-S038"][
                "canal_level"
            ],
            "03",
        )
        self.assertEqual(
            data["CANAL-S058"][
                "canal_level"
            ],
            "03",
        )

    def test_source_notes_use_normal_description(
        self,
    ):
        seed_official_master_data()

        with database.get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    master_key,
                    description
                FROM canal_units
                WHERE master_key IN (
                    'CANAL-S002',
                    'CANAL-S039',
                    'CANAL-S055',
                    'CANAL-S059'
                )
                """
            ).fetchall()

        notes = {
            row["master_key"]: row["description"]
            for row in rows
        }

        self.assertEqual(notes["CANAL-S002"], "移交通远乡管理")
        self.assertEqual(notes["CANAL-S039"], "移交西电")
        self.assertEqual(notes["CANAL-S055"], "向石门沟水库引水")
        self.assertEqual(notes["CANAL-S059"], "武川乡水利管理站管理")

    def test_second_seed_does_not_overwrite_manual_edit(
        self,
    ):
        seed_official_master_data()

        with database.get_connection() as connection:
            connection.execute(
                """
                UPDATE canal_units
                SET
                    name = ?
                WHERE master_key = ?
                """,
                (
                    "总干渠（甲方后续修改）",
                    "CANAL-G01",
                ),
            )

        result = (
            seed_official_master_data()
        )

        self.assertFalse(
            result["applied"]
        )
        self.assertTrue(
            result["already_applied"]
        )

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT name
                FROM canal_units
                WHERE master_key = ?
                """,
                ("CANAL-G01",),
            ).fetchone()

        self.assertEqual(
            row["name"],
            "总干渠（甲方后续修改）",
        )

    def test_existing_office_is_adopted_by_code_and_renamed(
        self,
    ):
        # 模拟正式种子导入前已经存在的旧简称资料。
        with database.get_connection() as connection:
            department = connection.execute(
                """
                INSERT INTO organization_units (
                    parent_id,
                    name,
                    unit_type,
                    business_code
                )
                VALUES (
                    NULL,
                    '东二干灌区处',
                    'department',
                    '3'
                )
                """
            )
            department_id = int(
                department.lastrowid
            )

            office = connection.execute(
                """
                INSERT INTO organization_units (
                    parent_id,
                    name,
                    unit_type,
                    business_code
                )
                VALUES (
                    ?,
                    '古山电灌水管所',
                    'water_office',
                    '04'
                )
                """,
                (department_id,),
            )
            office_id = int(
                office.lastrowid
            )

        seed_official_master_data()

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    name,
                    master_key
                FROM organization_units
                WHERE master_key = ?
                """,
                ("ORG-D03-O04",),
            ).fetchone()

        self.assertEqual(
            int(row["id"]),
            office_id,
        )
        self.assertEqual(
            row["name"],
            "古山电力提灌所",
        )

    def test_seed_history_is_written(
        self,
    ):
        seed_official_master_data()

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT seed_key
                FROM master_data_seed_history
                WHERE seed_key = ?
                """,
                (
                    OFFICIAL_MASTER_DATA_VERSION,
                ),
            ).fetchone()

        self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
