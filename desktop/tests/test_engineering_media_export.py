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


from services.engineering_media_export import (
    build_media_archive_filename,
    export_record_media,
)


def _record():
    return {
        "survey_record_id": 15,
        "business_code": (
            "1-01-03-02-001"
        ),
        "asset_name": "一号水闸",
        "canal_name": "一支渠",
        "engineering_position": (
            "K2+350"
        ),
    }


class EngineeringMediaExportTestCase(
    unittest.TestCase,
):
    def test_formal_filename_uses_archive_rule(
        self,
    ):
        media = {
            "sequence_no": 3,
            "part_name": "闸室",
            "absolute_path": Path(
                "C:/fake/abc.jpg"
            ),
            "original_filename": (
                "IMG_0003.JPG"
            ),
        }

        filename = (
            build_media_archive_filename(
                record=_record(),
                media=media,
            )
        )

        self.assertEqual(
            filename,
            (
                "一支渠-K2+350-"
                "一号水闸-闸室-03.jpg"
            ),
        )

    @patch(
        "services.engineering_media_export."
        "get_survey_media"
    )
    def test_export_copies_managed_media(
        self,
        mock_get_media,
    ):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)

            source = (
                temp_root
                / "managed"
                / "uid.jpg"
            )
            source.parent.mkdir()
            source.write_bytes(
                b"image-data"
            )

            mock_get_media.return_value = [
                {
                    "media_uid": "uid-1",
                    "media_kind": "photo",
                    "media_role": "overview",
                    "item_code": None,
                    "part_name": "闸室",
                    "sequence_no": 1,
                    "original_filename": (
                        "IMG_0001.jpg"
                    ),
                    "absolute_path": source,
                }
            ]

            media_root = (
                temp_root
                / "成果"
                / "03_影像资料"
            )
            media_root.mkdir(
                parents=True
            )

            result = export_record_media(
                record=_record(),
                media_root=media_root,
            )

            self.assertEqual(
                result["errors"],
                [],
            )
            self.assertEqual(
                len(result["entries"]),
                1,
            )

            exported = (
                temp_root
                / "成果"
                / result["entries"][0][
                    "relative_path"
                ]
            )

            self.assertTrue(
                exported.exists()
            )
            self.assertEqual(
                exported.read_bytes(),
                b"image-data",
            )

    @patch(
        "services.engineering_media_export."
        "get_survey_media"
    )
    def test_missing_managed_file_becomes_error(
        self,
        mock_get_media,
    ):
        mock_get_media.return_value = [
            {
                "media_uid": "uid-1",
                "media_kind": "photo",
                "media_role": "problem",
                "item_code": "gate_body",
                "part_name": "闸门",
                "sequence_no": 1,
                "original_filename": (
                    "missing.jpg"
                ),
                "absolute_path": Path(
                    "Z:/not-exist/"
                    "missing.jpg"
                ),
            }
        ]

        with tempfile.TemporaryDirectory() as temp:
            media_root = (
                Path(temp)
                / "03_影像资料"
            )
            media_root.mkdir()

            result = export_record_media(
                record=_record(),
                media_root=media_root,
            )

        self.assertEqual(
            len(result["errors"]),
            1,
        )
        self.assertEqual(
            result["entries"][0][
                "status"
            ],
            "失败",
        )


if __name__ == "__main__":
    unittest.main()
