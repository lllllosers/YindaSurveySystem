import gc
import sqlite3
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

from services.stable_identity import (
    ENTITY_IDENTITY_SPECS,
    get_entity_uid,
    get_identity_pair,
    resolve_entity_id,
)


class StableIdentityTestCase(
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
            / "stable_uid.db"
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

    def _init_fresh_database(self):
        database.init_database()

    def _insert_identity_chain(self):
        with database.get_connection() as connection:
            project_cursor = (
                connection.execute(
                    """
                    INSERT INTO projects (
                        name,
                        short_name,
                        status
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        "稳定身份测试项目",
                        "测试",
                        "active",
                    ),
                )
            )

            project_id = int(
                project_cursor.lastrowid
            )

            batch_cursor = (
                connection.execute(
                    """
                    INSERT INTO survey_batches (
                        project_id,
                        batch_name,
                        batch_code,
                        status
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        "2026年度调查",
                        "2026",
                        "active",
                    ),
                )
            )

            batch_id = int(
                batch_cursor.lastrowid
            )

            department_cursor = (
                connection.execute(
                    """
                    INSERT INTO organization_units (
                        name,
                        unit_type,
                        business_code
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        "测试处",
                        "department",
                        "1",
                    ),
                )
            )

            department_id = int(
                department_cursor.lastrowid
            )

            office_cursor = (
                connection.execute(
                    """
                    INSERT INTO organization_units (
                        parent_id,
                        name,
                        unit_type,
                        business_code
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        department_id,
                        "测试所",
                        "water_office",
                        "01",
                    ),
                )
            )

            office_id = int(
                office_cursor.lastrowid
            )

            canal_cursor = (
                connection.execute(
                    """
                    INSERT INTO canal_units (
                        name,
                        canal_level,
                        organization_unit_id
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        "测试支渠",
                        "03",
                        office_id,
                    ),
                )
            )

            canal_id = int(
                canal_cursor.lastrowid
            )

            form_cursor = (
                connection.execute(
                    """
                    INSERT INTO form_definitions (
                        form_code,
                        form_number,
                        form_name,
                        series,
                        record_type,
                        asset_type,
                        sort_order
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "uid_test_form",
                        "X",
                        "稳定身份测试表",
                        "series_2",
                        "engineering",
                        "uid_test_asset",
                        999,
                    ),
                )
            )

            form_id = int(
                form_cursor.lastrowid
            )

            version_cursor = (
                connection.execute(
                    """
                    INSERT INTO form_versions (
                        form_definition_id,
                        version_code,
                        schema_json,
                        is_current
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        form_id,
                        "V1",
                        "{}",
                        1,
                    ),
                )
            )

            version_id = int(
                version_cursor.lastrowid
            )

            asset_cursor = (
                connection.execute(
                    """
                    INSERT INTO engineering_assets (
                        project_id,
                        asset_name,
                        asset_type,
                        organization_unit_id,
                        canal_unit_id,
                        business_code,
                        first_survey_batch_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        "测试水闸",
                        "uid_test_asset",
                        office_id,
                        canal_id,
                        "1-01-03-02-001",
                        batch_id,
                    ),
                )
            )

            asset_id = int(
                asset_cursor.lastrowid
            )

            record_cursor = (
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
                        record_status
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        project_id,
                        batch_id,
                        version_id,
                        "engineering",
                        office_id,
                        canal_id,
                        asset_id,
                        "1-01-03-02-001",
                        "completed",
                    ),
                )
            )

            record_id = int(
                record_cursor.lastrowid
            )

        return {
            "project": project_id,
            "survey_batch": batch_id,
            "organization_unit": (
                office_id
            ),
            "canal_unit": canal_id,
            "engineering_asset": (
                asset_id
            ),
            "survey_record": record_id,
        }

    def test_fresh_inserts_receive_stable_uids(
        self,
    ):
        self._init_fresh_database()

        ids = (
            self._insert_identity_chain()
        )

        seen = set()

        for entity_type, local_id in (
            ids.items()
        ):
            uid = get_entity_uid(
                entity_type,
                local_id,
            )

            self.assertIsNotNone(uid)

            self.assertEqual(
                len(uid),
                32,
            )

            int(uid, 16)

            self.assertNotIn(
                uid,
                seen,
            )

            seen.add(uid)

            self.assertEqual(
                resolve_entity_id(
                    entity_type,
                    uid,
                ),
                local_id,
            )

    def test_identity_migration_backfills_legacy_row(
        self,
    ):
        database.DATA_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        connection = sqlite3.connect(
            database.DB_PATH
        )

        try:
            connection.execute(
                """
                CREATE TABLE projects (
                    id INTEGER PRIMARY KEY
                        AUTOINCREMENT,
                    name TEXT
                )
                """
            )

            connection.execute(
                """
                INSERT INTO projects (
                    name
                )
                VALUES (?)
                """,
                ("旧项目",),
            )

            connection.commit()

        finally:
            connection.close()

        database.init_database()

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    project_uid
                FROM projects
                WHERE id = 1
                """
            ).fetchone()

        self.assertIsNotNone(
            row
        )

        uid = str(
            row["project_uid"]
            or ""
        )

        self.assertEqual(
            len(uid),
            32,
        )

        int(uid, 16)

        first_uid = uid

        # 再次初始化不得重新生成 UID。
        database.init_database()

        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT project_uid
                FROM projects
                WHERE id = 1
                """
            ).fetchone()

        self.assertEqual(
            row["project_uid"],
            first_uid,
        )

    def test_stable_uid_is_immutable_after_assignment(
        self,
    ):
        self._init_fresh_database()

        ids = (
            self._insert_identity_chain()
        )

        project_id = ids[
            "project"
        ]

        original_uid = (
            get_entity_uid(
                "project",
                project_id,
            )
        )

        with self.assertRaises(
            sqlite3.IntegrityError
        ):
            with database.get_connection() as connection:
                connection.execute(
                    """
                    UPDATE projects
                    SET project_uid = ?
                    WHERE id = ?
                    """,
                    (
                        "0" * 32,
                        project_id,
                    ),
                )

        self.assertEqual(
            get_entity_uid(
                "project",
                project_id,
            ),
            original_uid,
        )

    def test_all_identity_columns_are_unique_indexed(
        self,
    ):
        self._init_fresh_database()

        with database.get_connection() as connection:
            for (
                _entity_type,
                (
                    table_name,
                    uid_column,
                ),
            ) in (
                ENTITY_IDENTITY_SPECS.items()
            ):
                columns = {
                    row["name"]
                    for row in (
                        connection.execute(
                            (
                                "PRAGMA table_info("
                                f"{table_name}"
                                ")"
                            )
                        ).fetchall()
                    )
                }

                self.assertIn(
                    uid_column,
                    columns,
                )

                indexes = (
                    connection.execute(
                        (
                            "PRAGMA index_list("
                            f"{table_name}"
                            ")"
                        )
                    ).fetchall()
                )

                unique_indexes = [
                    row
                    for row in indexes
                    if int(
                        row["unique"]
                    )
                    == 1
                ]

                indexed_columns = set()

                for index_row in (
                    unique_indexes
                ):
                    info = (
                        connection.execute(
                            (
                                "PRAGMA index_info("
                                f"{index_row['name']}"
                                ")"
                            )
                        ).fetchall()
                    )

                    indexed_columns.update(
                        row["name"]
                        for row in info
                    )

                self.assertIn(
                    uid_column,
                    indexed_columns,
                )

    def test_identity_pair_checks_consistency(
        self,
    ):
        self._init_fresh_database()

        ids = (
            self._insert_identity_chain()
        )

        project_id = ids[
            "project"
        ]

        uid = get_entity_uid(
            "project",
            project_id,
        )

        pair = get_identity_pair(
            "project",
            local_id=project_id,
            stable_uid=uid,
        )

        self.assertEqual(
            pair["local_id"],
            project_id,
        )

        self.assertEqual(
            pair["stable_uid"],
            uid,
        )


if __name__ == "__main__":
    unittest.main()
