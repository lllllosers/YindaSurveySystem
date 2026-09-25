import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from PySide6.QtWidgets import QApplication

from pages.data_query_page import DataQueryPage
from pages.engineering_asset_page import EngineeringAssetPage
from pages.engineering_asset_detail_dialog import (
    EngineeringAssetDetailDialog,
)


class RecordNavigationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    @patch(
        "pages.data_query_page.get_current_context",
        return_value=None,
    )
    def test_data_query_emits_selected_record_identity(
        self,
        _mock_context,
    ):
        page = DataQueryPage()

        record = {
            "survey_record_id": 101,
            "form_code": "form_2_2",
            "form_display_name": "附表2.2 水闸工程状况调查表",
            "batch_name": "测试批次",
            "business_code": "1-01-01-02-001",
            "asset_name": "测试水闸",
            "department_name": "测试处",
            "office_name": "测试所",
            "canal_name": "测试渠",
            "engineering_position": "CH1+000",
            "overall_grade": "B",
            "survey_date": "2026-09-19",
            "record_status": "completed",
            "updated_at": "2026-09-19 12:00:00",
        }

        page._render_records([record])
        page.table.selectRow(0)

        received = []
        page.open_survey_record_requested.connect(
            lambda form_code, record_id: received.append(
                (form_code, record_id)
            )
        )

        page.open_selected_record()

        self.assertEqual(
            received,
            [("form_2_2", 101)],
        )

        page.deleteLater()

    @patch(
        "pages.engineering_asset_page.get_current_context",
        return_value={
            "project_id": 1,
            "batch_id": 2,
        },
    )
    @patch(
        "pages.engineering_asset_page.get_engineering_assets",
        return_value=[
            {
                "engineering_asset_id": 5,
                "business_code": "1-01-01-02-001",
                "asset_name": "测试水闸",
                "asset_type": "sluice_gate",
                "department_name": "测试处",
                "office_name": "测试所",
                "canal_name": "测试渠",
                "single_stake_text": "CH1+000",
                "start_stake_text": None,
                "end_stake_text": None,
                "first_batch_name": "测试批次",
                "survey_status": "completed",
                "asset_status": "active",
                "survey_record_id": 55,
                "survey_form_code": "form_2_2",
            }
        ],
    )
    def test_engineering_ledger_double_click_opens_current_survey(
        self,
        _mock_assets,
        _mock_context,
    ):
        page = EngineeringAssetPage()

        received = []
        page.open_survey_record_requested.connect(
            lambda form_code, record_id: received.append(
                (form_code, record_id)
            )
        )

        page.handle_row_double_clicked(
            0,
            0,
        )

        self.assertEqual(
            received,
            [("form_2_2", 55)],
        )

        page.deleteLater()

    @patch(
        "pages.engineering_asset_detail_dialog.get_engineering_asset_history",
        return_value=[
            {
                "survey_record_id": 77,
                "business_code": "1-01-01-02-001",
                "survey_date": "2026-09-19",
                "overall_grade": "B",
                "record_status": "completed",
                "updated_at": "2026-09-19 12:00:00",
                "batch_name": "测试批次",
                "form_code": "form_2_2",
                "form_number": "2.2",
                "form_name": "水闸工程状况调查表",
                "version_code": "V1",
                "version_name": "V1",
            }
        ],
    )
    @patch(
        "pages.engineering_asset_detail_dialog.get_engineering_asset_detail",
        return_value={
            "asset_type": "sluice_gate",
            "canal_level": "03",
            "single_stake_text": "CH1+000",
            "start_stake_text": None,
            "end_stake_text": None,
            "asset_status": "active",
            "business_code": "1-01-01-02-001",
            "asset_name": "测试水闸",
            "department_name": "测试处",
            "office_name": "测试所",
            "canal_name": "测试渠",
            "first_batch_name": "测试批次",
        },
    )
    def test_asset_history_can_open_full_record(
        self,
        _mock_detail,
        _mock_history,
    ):
        dialog = EngineeringAssetDetailDialog(
            engineering_asset_id=5,
        )

        dialog.history_table.selectRow(0)

        received = []
        dialog.open_survey_record_requested.connect(
            lambda form_code, record_id: received.append(
                (form_code, record_id)
            )
        )

        dialog.open_selected_history_record()

        self.assertEqual(
            received,
            [("form_2_2", 77)],
        )

        dialog.deleteLater()

    def test_main_wires_record_navigation(self):
        source = (
            PROJECT_ROOT
            / "src"
            / "main.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "def open_survey_record(",
            source,
        )

        self.assertGreaterEqual(
            source.count(
                "open_survey_record_requested.connect"
            ),
            2,
        )


if __name__ == "__main__":
    unittest.main()
