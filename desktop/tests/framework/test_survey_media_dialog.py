import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)


PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from PySide6.QtWidgets import QApplication

from pages.components.survey_media_dialog import (
    SurveyMediaDialog,
)


class SurveyMediaDialogTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    @patch(
        "pages.components."
        "survey_media_dialog."
        "get_engineering_form_definition"
    )
    @patch(
        "pages.components."
        "survey_media_dialog."
        "get_survey_media"
    )
    def test_dialog_loads_media_rows(
        self,
        mock_get_media,
        mock_get_definition,
    ):
        mock_get_definition.return_value = None

        mock_get_media.return_value = [
            {
                "id": 7,
                "media_kind": "photo",
                "media_role": "overview",
                "part_name": "闸室",
                "item_code": None,
                "sequence_no": 2,
                "original_filename": (
                    "IMG_0001.jpg"
                ),
                "file_size": 2048,
                "captured_at": (
                    "2026-09-17 10:30"
                ),
                "notes": "全景",
                "absolute_path": Path(
                    "C:/fake/IMG_0001.jpg"
                ),
            }
        ]

        dialog = SurveyMediaDialog(
            survey_record_id=123,
            form_code="form_2_2",
            record_summary={
                "business_code": (
                    "1-01-03-02-001"
                ),
                "asset_name": "测试闸",
            },
        )

        try:
            self.assertEqual(
                dialog.table.rowCount(),
                1,
            )
            self.assertEqual(
                dialog.table.item(
                    0,
                    0,
                ).text(),
                "2",
            )
            self.assertEqual(
                dialog.table.item(
                    0,
                    1,
                ).text(),
                "照片",
            )
            self.assertEqual(
                dialog.table.item(
                    0,
                    2,
                ).text(),
                "全景",
            )
            self.assertIn(
                "照片 1",
                dialog.count_label.text(),
            )

            dialog.table.selectRow(0)

            selected = (
                dialog._selected_media()
            )

            self.assertEqual(
                selected["id"],
                7,
            )

        finally:
            dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
