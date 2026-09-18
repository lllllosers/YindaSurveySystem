import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from services.engineering_record_delete import (
    delete_engineering_survey_record_with_media,
)


class EngineeringRecordDeleteTestCase(
    unittest.TestCase,
):
    def test_files_are_removed_after_database_delete(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp:
            media_path = (
                Path(temp)
                / "record_1"
                / "media.jpg"
            )

            media_path.parent.mkdir()
            media_path.write_bytes(
                b"media"
            )

            with patch(
                "services.engineering_record_delete."
                "get_survey_media",
                return_value=[
                    {
                        "original_filename": (
                            "media.jpg"
                        ),
                        "absolute_path": (
                            media_path
                        ),
                    }
                ],
            ), patch(
                "services.engineering_record_delete."
                "delete_engineering_survey_record",
                return_value={
                    "asset_deleted": True,
                },
            ):
                result = (
                    delete_engineering_survey_record_with_media(
                        survey_record_id=1,
                        form_code="form_2_2",
                    )
                )

            self.assertFalse(
                media_path.exists()
            )
            self.assertEqual(
                result[
                    "media_file_deleted_count"
                ],
                1,
            )
            self.assertEqual(
                result[
                    "media_cleanup_errors"
                ],
                (),
            )

    def test_database_failure_keeps_media_file(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp:
            media_path = (
                Path(temp)
                / "media.jpg"
            )

            media_path.write_bytes(
                b"media"
            )

            with patch(
                "services.engineering_record_delete."
                "get_survey_media",
                return_value=[
                    {
                        "original_filename": (
                            "media.jpg"
                        ),
                        "absolute_path": (
                            media_path
                        ),
                    }
                ],
            ), patch(
                "services.engineering_record_delete."
                "delete_engineering_survey_record",
                side_effect=ValueError(
                    "模拟数据库删除失败"
                ),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "模拟数据库删除失败",
                ):
                    delete_engineering_survey_record_with_media(
                        survey_record_id=1,
                        form_code="form_2_2",
                    )

            self.assertTrue(
                media_path.exists()
            )


if __name__ == "__main__":
    unittest.main()
