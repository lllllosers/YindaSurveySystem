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

from pages.data_query_page import (
    DataQueryPage,
)


class DataQueryDynamicGradesTestCase(
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

    def setUp(
        self,
    ):
        self.context_patch = patch(
            "pages.data_query_page."
            "get_current_context",
            return_value=None,
        )

        self.context_patch.start()

        self.page = DataQueryPage()

    def tearDown(
        self,
    ):
        self.page.deleteLater()
        self.context_patch.stop()

    def test_grade_filter_follows_selected_form_definition(
        self,
    ):
        def grade_options(
            form_code,
        ):
            if form_code == "form_2_99":
                return (
                    "A",
                    "B",
                    "C",
                )

            return (
                "A",
                "B",
                "C",
                "D",
            )

        # form_combo 已连接 currentIndexChanged。
        # 构造测试用虚拟 form_code 时必须先 patch，
        # 避免 Qt signal 在测试夹具准备阶段调用真实 Registry。
        with patch(
            "pages.data_query_page."
            "get_engineering_grade_options",
            side_effect=grade_options,
        ):
            self.page.form_combo.clear()
            self.page.form_combo.addItem(
                "全部工程调查表",
                None,
            )
            self.page.form_combo.addItem(
                "三级评价测试表",
                "form_2_99",
            )

            self.page.form_combo.setCurrentIndex(
                0
            )
            self.page._refresh_grade_options()

            self.assertEqual(
                tuple(
                    self.page.grade_combo.itemData(
                        index
                    )
                    for index in range(
                        1,
                        self.page.grade_combo.count(),
                    )
                ),
                (
                    "A",
                    "B",
                    "C",
                    "D",
                ),
            )

            self.page.form_combo.setCurrentIndex(
                1
            )

            self.assertEqual(
                tuple(
                    self.page.grade_combo.itemData(
                        index
                    )
                    for index in range(
                        1,
                        self.page.grade_combo.count(),
                    )
                ),
                (
                    "A",
                    "B",
                    "C",
                ),
            )

    def test_statistics_only_show_current_grade_options(
        self,
    ):
        records = [
            {
                "record_status": "draft",
                "overall_grade": "A",
            },
            {
                "record_status": "completed",
                "overall_grade": "B",
            },
            {
                "record_status": "completed",
                "overall_grade": "C",
            },
        ]

        # addItem() 在空 QComboBox 上会触发
        # currentIndexChanged；patch 必须覆盖夹具构造过程。
        with patch(
            "pages.data_query_page."
            "get_engineering_grade_options",
            return_value=(
                "A",
                "B",
                "C",
            ),
        ):
            self.page.form_combo.clear()
            self.page.form_combo.addItem(
                "三级评价测试表",
                "form_2_99",
            )

            self.page._update_statistics(
                records
            )

        text = (
            self.page.statistics_label.text()
        )

        self.assertIn(
            "A 1",
            text,
        )
        self.assertIn(
            "B 1",
            text,
        )
        self.assertIn(
            "C 1",
            text,
        )
        self.assertNotIn(
            "|  D ",
            text,
        )


if __name__ == "__main__":
    unittest.main()
