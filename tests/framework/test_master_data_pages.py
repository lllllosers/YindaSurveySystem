import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from PySide6.QtWidgets import QApplication
from pages.canal_page import CanalPage
from pages.organization_page import OrganizationPage


class MasterDataPagesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @patch("pages.canal_page.get_canal_management_summary_map")
    @patch("pages.canal_page.get_canal_sort_order_map")
    @patch("pages.canal_page.get_canal_units")
    def test_canal_page_uses_official_sort_and_description(
        self, mock_canals, mock_orders, mock_summaries
    ):
        mock_canals.return_value = [
            {
                "id": 2,
                "name": "后显示",
                "canal_level": "03",
                "organization_name": "测试管理单位",
                "description": "备注内容",
                "status": "active",
                "parent_id": None,
            },
            {
                "id": 1,
                "name": "先显示",
                "canal_level": "01",
                "organization_name": "",
                "description": None,
                "status": "active",
                "parent_id": None,
            },
        ]
        mock_orders.return_value = {1: 10, 2: 20}
        mock_summaries.return_value = {
            2: "测试管理单位（全渠）",
        }
        page = CanalPage()
        try:
            self.assertEqual(page.tree.columnCount(), 5)
            self.assertEqual(page.tree.topLevelItem(0).text(0), "先显示")
            self.assertEqual(page.tree.topLevelItem(1).text(3), "备注内容")
            self.assertEqual(page.tree.topLevelItem(1).text(4), "启用")
        finally:
            page.deleteLater()

    @patch("pages.organization_page.get_organization_sort_order_map")
    @patch("pages.organization_page.get_water_offices")
    @patch("pages.organization_page.get_departments")
    def test_organization_page_uses_official_sort(
        self, mock_departments, mock_offices, mock_orders
    ):
        mock_departments.return_value = [
            {"id": 2, "name": "第二处", "business_code": "2", "status": "active"},
            {"id": 1, "name": "第一处", "business_code": "1", "status": "active"},
        ]
        mock_offices.side_effect = lambda department_id: [
            {
                "id": 20 if department_id == 2 else 10,
                "name": "第二管理单位" if department_id == 2 else "第一管理单位",
                "business_code": "01",
                "status": "active",
            }
        ]
        mock_orders.return_value = {1: 10, 2: 20, 10: 11, 20: 21}
        page = OrganizationPage()
        try:
            self.assertEqual(page.tree.topLevelItem(0).text(0), "第一处")
            child = page.tree.topLevelItem(0).child(0)
            self.assertEqual(child.text(1), "管理单位")
        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
