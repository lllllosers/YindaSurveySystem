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

from services.survey_media import (
    delete_survey_media,
    get_media_record,
    get_survey_media,
    import_survey_media,
    update_media_metadata,
)


class SurveyMediaTestCase(
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
            / "test_media.db"
        )

        database.init_database()
        database.create_initial_forms()

        self.survey_record_id = (
            self._create_record()
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

    def _create_record(self):
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
                        "影像测试项目",
                        "影像测试",
                        "active",
                    ),
                )
            )

            project_id = (
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
                        "2026调查",
                        "MEDIA_2026",
                        "active",
                    ),
                )
            )

            batch_id = (
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

            department_id = (
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

            office_id = (
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

            canal_id = (
                canal_cursor.lastrowid
            )

            form_version = (
                connection.execute(
                    """
                    SELECT
                        fv.id
                    FROM form_versions fv
                    JOIN form_definitions fd
                      ON fv.form_definition_id
                       = fd.id
                    WHERE fd.form_code = ?
                      AND fv.is_current = 1
                    LIMIT 1
                    """,
                    ("form_2_2",),
                ).fetchone()
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
                        "sluice_gate",
                        office_id,
                        canal_id,
                        "1-01-03-02-001",
                        batch_id,
                    ),
                )
            )

            asset_id = (
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
                        form_version["id"],
                        "engineering",
                        office_id,
                        canal_id,
                        asset_id,
                        "1-01-03-02-001",
                        "completed",
                    ),
                )
            )

            return int(
                record_cursor.lastrowid
            )

    def _source_file(
        self,
        name="现场照片.JPG",
        content=b"media-test-content",
    ):
        source = (
            self.temp_root
            / name
        )

        source.write_bytes(content)

        return source

    def test_schema_contains_survey_media(
        self,
    ):
        with database.get_connection() as connection:
            row = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'survey_media'
                """
            ).fetchone()

        self.assertIsNotNone(row)

    def test_import_copies_file_and_saves_metadata(
        self,
    ):
        source = self._source_file()

        result = import_survey_media(
            survey_record_id=(
                self.survey_record_id
            ),
            source_file=source,
            media_role="overview",
            part_name="闸室",
            sequence_no=2,
            notes="测试照片",
        )

        self.assertTrue(
            result["absolute_path"].exists()
        )

        self.assertTrue(
            source.exists()
        )

        media = get_media_record(
            result["media_id"]
        )

        self.assertEqual(
            media["media_kind"],
            "photo",
        )
        self.assertEqual(
            media["media_role"],
            "overview",
        )
        self.assertEqual(
            media["part_name"],
            "闸室",
        )
        self.assertEqual(
            media["sequence_no"],
            2,
        )
        self.assertEqual(
            media["original_filename"],
            "现场照片.JPG",
        )

    def test_duplicate_same_file_is_rejected(
        self,
    ):
        source = self._source_file()

        import_survey_media(
            survey_record_id=(
                self.survey_record_id
            ),
            source_file=source,
        )

        with self.assertRaisesRegex(
            ValueError,
            "已经导入过相同影像",
        ):
            import_survey_media(
                survey_record_id=(
                    self.survey_record_id
                ),
                source_file=source,
            )

    def test_list_is_ordered_by_sequence(
        self,
    ):
        first = self._source_file(
            "第一张.jpg",
            b"first",
        )
        second = self._source_file(
            "第二张.jpg",
            b"second",
        )

        import_survey_media(
            survey_record_id=(
                self.survey_record_id
            ),
            source_file=first,
            sequence_no=20,
        )

        import_survey_media(
            survey_record_id=(
                self.survey_record_id
            ),
            source_file=second,
            sequence_no=10,
        )

        media = get_survey_media(
            self.survey_record_id
        )

        self.assertEqual(
            [
                item["sequence_no"]
                for item in media
            ],
            [10, 20],
        )

    def test_update_metadata_does_not_rename_managed_file(
        self,
    ):
        result = import_survey_media(
            survey_record_id=(
                self.survey_record_id
            ),
            source_file=(
                self._source_file()
            ),
        )

        original_path = (
            result["absolute_path"]
        )

        update_media_metadata(
            result["media_id"],
            media_role="problem",
            item_code="gate_body",
            part_name="闸门",
            sequence_no=7,
            captured_at=(
                "2026-09-17 10:30"
            ),
            notes="裂缝",
        )

        media = get_media_record(
            result["media_id"]
        )

        self.assertEqual(
            media["media_role"],
            "problem",
        )
        self.assertEqual(
            media["item_code"],
            "gate_body",
        )
        self.assertEqual(
            media["sequence_no"],
            7,
        )
        self.assertEqual(
            media["absolute_path"],
            original_path,
        )
        self.assertTrue(
            original_path.exists()
        )

    def test_delete_removes_row_and_managed_file(
        self,
    ):
        result = import_survey_media(
            survey_record_id=(
                self.survey_record_id
            ),
            source_file=(
                self._source_file()
            ),
        )

        managed_path = (
            result["absolute_path"]
        )

        delete_survey_media(
            result["media_id"]
        )

        self.assertIsNone(
            get_media_record(
                result["media_id"]
            )
        )
        self.assertFalse(
            managed_path.exists()
        )

    def test_unknown_extension_is_rejected(
        self,
    ):
        source = self._source_file(
            "不是影像.txt"
        )

        with self.assertRaisesRegex(
            ValueError,
            "照片或视频格式",
        ):
            import_survey_media(
                survey_record_id=(
                    self.survey_record_id
                ),
                source_file=source,
            )


if __name__ == "__main__":
    unittest.main()
