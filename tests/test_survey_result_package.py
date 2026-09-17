import gc
from hashlib import sha256
import json
import sys
import tempfile
import unittest
from pathlib import Path
import zipfile


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
from services.survey_media import (
    import_survey_media,
)
from services.survey_result_package import (
    SurveyResultExportRequest,
    export_survey_result_package,
)


class SurveyResultPackageTestCase(
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
            / "result_package.db"
        )

        initialize_application_database()

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
                        "2026年调查项目",
                        "2026调查",
                        "active",
                    ),
                )
            )

            self.project_id = int(
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
                        self.project_id,
                        "2026年调查批次",
                        "2026",
                        "active",
                    ),
                )
            )

            self.batch_id = int(
                batch_cursor.lastrowid
            )

            office = connection.execute(
                """
                SELECT id
                FROM organization_units
                WHERE master_key = ?
                """,
                (
                    "ORG-D01-O03",
                ),
            ).fetchone()

            canal = connection.execute(
                """
                SELECT id
                FROM canal_units
                WHERE master_key = ?
                """,
                (
                    "CANAL-S001",
                ),
            ).fetchone()

            form = connection.execute(
                """
                SELECT
                    fv.id AS form_version_id,
                    fd.asset_type
                FROM form_definitions AS fd
                JOIN form_versions AS fv
                  ON fv.form_definition_id = fd.id
                WHERE fd.series = 'series_2'
                  AND fd.record_type = 'engineering'
                  AND fd.is_enabled = 1
                  AND fv.is_current = 1
                ORDER BY fd.sort_order, fd.id
                LIMIT 1
                """
            ).fetchone()

            self.office_id = int(
                office["id"]
            )
            self.canal_id = int(
                canal["id"]
            )
            self.form_version_id = int(
                form[
                    "form_version_id"
                ]
            )
            self.asset_type = str(
                form["asset_type"]
                or "test_asset"
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
                        first_survey_batch_id,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.project_id,
                        "测试工程",
                        self.asset_type,
                        self.office_id,
                        self.canal_id,
                        "1-03-03-01-001",
                        self.batch_id,
                        "active",
                    ),
                )
            )

            self.asset_id = int(
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
                        survey_date,
                        overall_grade,
                        survey_comment,
                        record_status,
                        record_data_json
                    )
                    VALUES (
                        ?, ?, ?, 'engineering',
                        ?, ?, ?, ?, ?,
                        ?, ?, 'completed', ?
                    )
                    """,
                    (
                        self.project_id,
                        self.batch_id,
                        self.form_version_id,
                        self.office_id,
                        self.canal_id,
                        self.asset_id,
                        "1-03-03-01-001",
                        "2026-09-17",
                        "B",
                        "测试完成记录",
                        json.dumps(
                            {
                                "demo": "value",
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )
            )

            self.record_id = int(
                record_cursor.lastrowid
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
                    self.record_id,
                    "A01",
                    "主体",
                    "测试分项",
                    "B",
                    "测试描述",
                    "测试备注",
                ),
            )

        self.media_source = (
            self.temp_root
            / "现场照片.jpg"
        )

        self.media_bytes = (
            b"fake-jpeg-binary-content"
        )

        self.media_source.write_bytes(
            self.media_bytes
        )

        self.media_result = (
            import_survey_media(
                survey_record_id=(
                    self.record_id
                ),
                source_file=(
                    self.media_source
                ),
                media_role="overview",
                part_name="整体",
                sequence_no=1,
            )
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

    def _export(
        self,
        *,
        filename="调查成果.ydresult",
        record_ids=None,
    ):
        return (
            export_survey_result_package(
                SurveyResultExportRequest(
                    project_id=(
                        self.project_id
                    ),
                    survey_batch_id=(
                        self.batch_id
                    ),
                    survey_record_ids=(
                        tuple(
                            record_ids
                            if record_ids
                            is not None
                            else (
                                self.record_id,
                            )
                        )
                    ),
                    output_path=(
                        self.temp_root
                        / filename
                    ),
                    result_name=(
                        "通远水管所调查成果"
                    ),
                    source_task_uid=(
                        "task-demo-001"
                    ),
                    creator="测试人员",
                    notes="Stage 11.1 测试",
                )
            )
        )

    def test_exports_expected_result_package(
        self,
    ):
        result = self._export()

        self.assertTrue(
            result.output_path.exists()
        )
        self.assertEqual(
            result.output_path.suffix,
            ".ydresult",
        )
        self.assertEqual(
            result.survey_record_count,
            1,
        )
        self.assertEqual(
            result.engineering_asset_count,
            1,
        )
        self.assertEqual(
            result.inspection_result_count,
            1,
        )
        self.assertEqual(
            result.media_count,
            1,
        )

        media_uid = (
            self.media_result[
                "media_uid"
            ]
        )

        media_package_path = (
            f"media/{media_uid}.jpg"
        )

        with zipfile.ZipFile(
            result.output_path,
            "r",
        ) as archive:
            names = set(
                archive.namelist()
            )

            self.assertEqual(
                names,
                {
                    "manifest.json",
                    "result.json",
                    (
                        "data/"
                        "engineering_assets.json"
                    ),
                    (
                        "data/"
                        "survey_records.json"
                    ),
                    (
                        "data/"
                        "inspection_results.json"
                    ),
                    (
                        "data/"
                        "survey_media.json"
                    ),
                    media_package_path,
                },
            )

            self.assertEqual(
                archive.read(
                    media_package_path
                ),
                self.media_bytes,
            )

    def test_manifest_tracks_all_payload_and_media_hashes(
        self,
    ):
        result = self._export()

        with zipfile.ZipFile(
            result.output_path,
            "r",
        ) as archive:
            manifest = json.loads(
                archive.read(
                    "manifest.json"
                )
            )

            self.assertEqual(
                manifest[
                    "package_kind"
                ],
                "survey_result",
            )
            self.assertEqual(
                manifest[
                    "result_uid"
                ],
                result.result_uid,
            )
            self.assertEqual(
                manifest[
                    "source_task_uid"
                ],
                "task-demo-001",
            )

            paths = {
                entry["path"]
                for entry in manifest[
                    "files"
                ]
            }

            self.assertIn(
                "result.json",
                paths,
            )

            self.assertTrue(
                any(
                    path.startswith(
                        "media/"
                    )
                    for path in paths
                )
            )

            for entry in manifest[
                "files"
            ]:
                content = archive.read(
                    entry["path"]
                )

                self.assertEqual(
                    len(content),
                    entry["size"],
                )

                self.assertEqual(
                    sha256(
                        content
                    ).hexdigest(),
                    entry["sha256"],
                )

    def test_export_uses_stable_uids_not_local_ids(
        self,
    ):
        result = self._export()

        with zipfile.ZipFile(
            result.output_path,
            "r",
        ) as archive:
            assets = json.loads(
                archive.read(
                    (
                        "data/"
                        "engineering_assets.json"
                    )
                )
            )["items"]

            records = json.loads(
                archive.read(
                    (
                        "data/"
                        "survey_records.json"
                    )
                )
            )["items"]

            inspections = json.loads(
                archive.read(
                    (
                        "data/"
                        "inspection_results.json"
                    )
                )
            )["items"]

            media = json.loads(
                archive.read(
                    (
                        "data/"
                        "survey_media.json"
                    )
                )
            )["items"]

        self.assertIn(
            "engineering_asset_uid",
            assets[0],
        )
        self.assertNotIn(
            "id",
            assets[0],
        )

        self.assertIn(
            "survey_record_uid",
            records[0],
        )
        self.assertNotIn(
            "id",
            records[0],
        )
        self.assertNotIn(
            "engineering_asset_id",
            records[0],
        )
        self.assertIn(
            "engineering_asset_uid",
            records[0],
        )

        self.assertIn(
            "survey_record_uid",
            inspections[0],
        )
        self.assertNotIn(
            "survey_record_id",
            inspections[0],
        )

        self.assertIn(
            "media_uid",
            media[0],
        )
        self.assertIn(
            "survey_record_uid",
            media[0],
        )
        self.assertNotIn(
            "survey_record_id",
            media[0],
        )
        self.assertNotIn(
            "stored_relative_path",
            media[0],
        )
        self.assertIn(
            "package_path",
            media[0],
        )

    def test_missing_managed_media_file_blocks_export(
        self,
    ):
        managed_path = Path(
            self.media_result[
                "absolute_path"
            ]
        )

        managed_path.unlink()

        with self.assertRaises(
            FileNotFoundError
        ):
            self._export()

    def test_tampered_managed_media_blocks_export(
        self,
    ):
        managed_path = Path(
            self.media_result[
                "absolute_path"
            ]
        )

        managed_path.write_bytes(
            b"different-content-same-purpose"
        )

        with self.assertRaises(
            ValueError
        ):
            self._export()

    def test_draft_record_cannot_be_exported(
        self,
    ):
        with database.get_connection() as connection:
            connection.execute(
                """
                UPDATE survey_records
                SET record_status = 'draft'
                WHERE id = ?
                """,
                (
                    self.record_id,
                ),
            )

        with self.assertRaises(
            ValueError
        ) as context:
            self._export()

        self.assertIn(
            "已完成",
            str(context.exception),
        )

    def test_missing_extension_is_added(
        self,
    ):
        result = self._export(
            filename="调查成果"
        )

        self.assertEqual(
            result.output_path.name,
            "调查成果.ydresult",
        )

    def test_existing_target_is_not_overwritten(
        self,
    ):
        result = self._export()

        before = (
            result.output_path
            .read_bytes()
        )

        with self.assertRaises(
            FileExistsError
        ):
            self._export()

        after = (
            result.output_path
            .read_bytes()
        )

        self.assertEqual(
            before,
            after,
        )


if __name__ == "__main__":
    unittest.main()
