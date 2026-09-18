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


from PySide6.QtWidgets import (
    QApplication,
)

from pages.canal_page import (
    CanalPage,
)


class CanalManagementScopePageTestCase(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(
        cls,
    ):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    @patch(
        "pages.canal_page."
        "get_canal_management_summary_map"
    )
    @patch(
        "pages.canal_page."
        "get_canal_sort_order_map"
    )
    @patch(
        "pages.canal_page."
        "get_canal_units"
    )
    def test_tree_uses_management_scope_summary(
        self,
        mock_canals,
        mock_orders,
        mock_summaries,
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

        mock_orders.return_value = {
            1: 10,
        }

        mock_summaries.return_value = {
            1: (
                "渠首水管所（分段/边界未知）；"
                "天王沟水管所（分段/边界未知）"
            )
        }

        page = CanalPage()

        try:
            self.assertEqual(
                page.tree.headerItem().text(
                    2
                ),
                "管理范围",
            )

            self.assertEqual(
                page.tree.topLevelItem(
                    0
                ).text(
                    2
                ),
                (
                    "渠首水管所（分段/边界未知）；"
                    "天王沟水管所（分段/边界未知）"
                ),
            )

            self.assertTrue(
                hasattr(
                    page,
                    "management_scope_button",
                )
            )

        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
