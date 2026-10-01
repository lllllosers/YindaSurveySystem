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
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from PySide6.QtWidgets import (
    QApplication,
    QTreeWidget,
)

from pages.home_page import HomePage


class HomeProgressDashboardTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def test_home_progress_tree_shows_department_and_office(self):
        progress = {
            "project_id": 1,
            "survey_batch_id": 2,
            "total_records": 4,
            "completed_records": 3,
            "draft_records": 1,
            "completion_rate": 75.0,
            "grades": {
                "A": 1,
                "B": 1,
                "C": 1,
                "D": 0,
            },
            "departments": [
                {
                    "department_id": 10,
                    "department_name": "测试处",
                    "total_records": 4,
                    "completed_records": 3,
                    "draft_records": 1,
                    "completion_rate": 75.0,
                    "grades": {
                        "A": 1,
                        "B": 1,
                        "C": 1,
                        "D": 0,
                    },
                    "offices": [
                        {
                            "office_id": 11,
                            "office_name": "测试水管所",
                            "total_records": 4,
                            "completed_records": 3,
                            "draft_records": 1,
                            "completion_rate": 75.0,
                            "grades": {
                                "A": 1,
                                "B": 1,
                                "C": 1,
                                "D": 0,
                            },
                        },
                    ],
                },
            ],
        }

        with (
            patch(
                "pages.home_page.get_current_context",
                return_value={
                    "project_id": 1,
                    "project_name": "测试项目",
                    "batch_id": 2,
                    "batch_name": "测试批次",
                },
            ),
            patch(
                "pages.home_page.get_survey_readiness",
                return_value={
                    "ready": True,
                    "missing": [],
                },
            ),
            patch(
                "pages.home_page.get_engineering_progress",
                return_value=progress,
            ),
        ):
            page = HomePage()

        try:
            tree = page.findChild(
                QTreeWidget,
                "progressTree",
            )

            self.assertIsNotNone(tree)
            self.assertEqual(
                tree.topLevelItemCount(),
                1,
            )

            department = tree.topLevelItem(0)
            self.assertEqual(
                department.text(0),
                "测试处",
            )
            self.assertEqual(
                department.text(2),
                "3",
            )
            self.assertEqual(
                department.text(4),
                "75.0%",
            )

            office = department.child(0)
            self.assertEqual(
                office.text(0),
                "测试水管所",
            )
            self.assertEqual(
                office.text(1),
                "4",
            )

        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
