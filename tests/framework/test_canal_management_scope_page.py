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
    sys.path.insert(0, str(SRC_DIR))


from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from pages.canal_page import CanalPage


class CanalManagementScopePageTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    @patch(
        "pages.canal_page."
        "get_management_scopes_for_admin"
    )
    @patch(
        "pages.canal_page."
        "get_canal_sort_order_map"
    )
    @patch(
        "pages.canal_page."
        "get_canal_units"
    )
    def test_segment_scopes_render_as_scope_children(
        self,
        mock_canals,
        mock_orders,
        mock_scopes,
    ):
        mock_canals.return_value = [
            {
                "id": 1,
                "name": "总干渠",
                "canal_level": "01",
                "organization_name": "",
                "description": None,
                "status": "active",
                "parent_id": None,
            }
        ]
        mock_orders.return_value = {1: 10}
        mock_scopes.return_value = [
            {
                "id": 11,
                "management_scope_uid": "scope-1",
                "organization_name": "渠首水管所",
                "range_mode": "segment_unknown",
                "start_stake_text": None,
                "start_stake_value": None,
                "end_stake_text": None,
                "end_stake_value": None,
                "description": None,
                "status": "active",
            },
            {
                "id": 12,
                "management_scope_uid": "scope-2",
                "organization_name": "天王沟水管所",
                "range_mode": "segment_unknown",
                "start_stake_text": None,
                "start_stake_value": None,
                "end_stake_text": None,
                "end_stake_value": None,
                "description": None,
                "status": "active",
            },
        ]

        page = CanalPage()

        try:
            root = page.tree.topLevelItem(0)

            self.assertEqual(
                page.tree.headerItem().text(1),
                "类型",
            )
            self.assertEqual(
                page.tree.headerItem().text(2),
                "管理单位（范围）",
            )
            self.assertEqual(root.text(0), "总干渠")
            self.assertEqual(root.text(1), "干渠")
            self.assertEqual(
                root.text(2),
                "2 个分管段",
            )
            self.assertEqual(root.childCount(), 2)

            first = root.child(0)
            second = root.child(1)

            self.assertEqual(first.text(1), "分管段")
            self.assertEqual(
                first.text(2),
                "渠首水管所（边界未知）",
            )
            self.assertEqual(
                second.text(2),
                "天王沟水管所（边界未知）",
            )

            first_data = first.data(
                0,
                Qt.ItemDataRole.UserRole,
            )
            self.assertEqual(
                first_data["node_type"],
                "management_scope",
            )
            self.assertEqual(
                first_data["canal_id"],
                1,
            )
        finally:
            page.deleteLater()

    @patch(
        "pages.canal_page."
        "get_management_scopes_for_admin"
    )
    @patch(
        "pages.canal_page."
        "get_canal_sort_order_map"
    )
    @patch(
        "pages.canal_page."
        "get_canal_units"
    )
    def test_single_whole_scope_stays_compact(
        self,
        mock_canals,
        mock_orders,
        mock_scopes,
    ):
        mock_canals.return_value = [
            {
                "id": 2,
                "name": "测试支渠",
                "canal_level": "03",
                "organization_name": "",
                "description": None,
                "status": "active",
                "parent_id": None,
            }
        ]
        mock_orders.return_value = {2: 10}
        mock_scopes.return_value = [
            {
                "id": 21,
                "management_scope_uid": "scope-whole",
                "organization_name": "测试水管所",
                "range_mode": "whole",
                "start_stake_text": None,
                "start_stake_value": None,
                "end_stake_text": None,
                "end_stake_value": None,
                "description": None,
                "status": "active",
            }
        ]

        page = CanalPage()

        try:
            root = page.tree.topLevelItem(0)

            self.assertEqual(root.childCount(), 0)
            self.assertEqual(
                root.text(2),
                "测试水管所（全渠）",
            )
        finally:
            page.deleteLater()

    @patch(
        "pages.canal_page."
        "get_management_scopes_for_admin"
    )
    @patch(
        "pages.canal_page."
        "get_canal_sort_order_map"
    )
    @patch(
        "pages.canal_page."
        "get_canal_units"
    )
    def test_scope_selection_disables_canal_actions(
        self,
        mock_canals,
        mock_orders,
        mock_scopes,
    ):
        mock_canals.return_value = [
            {
                "id": 1,
                "name": "总干渠",
                "canal_level": "01",
                "organization_name": "",
                "description": None,
                "status": "active",
                "parent_id": None,
            }
        ]
        mock_orders.return_value = {1: 10}
        mock_scopes.return_value = [
            {
                "id": 11,
                "management_scope_uid": "scope-1",
                "organization_name": "渠首水管所",
                "range_mode": "segment_unknown",
                "start_stake_text": None,
                "start_stake_value": None,
                "end_stake_text": None,
                "end_stake_value": None,
                "description": None,
                "status": "active",
            }
        ]

        page = CanalPage()

        try:
            scope_item = (
                page.tree.topLevelItem(0).child(0)
            )
            page.tree.setCurrentItem(scope_item)
            self.app.processEvents()
            page.update_action_buttons()

            self.assertFalse(
                page.edit_button.isEnabled()
            )
            self.assertFalse(
                page.status_button.isEnabled()
            )
            self.assertFalse(
                page.delete_button.isEnabled()
            )
            self.assertTrue(
                page.management_scope_button.isEnabled()
            )
            self.assertEqual(
                page.management_scope_button.text(),
                "编辑分管段",
            )
        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
