import os
import sys
import unittest
from pathlib import Path

# Qt 测试不依赖实体显示器。
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
)

from pages.components.evaluation_section import (
    EvaluationSection,
)

TEST_ITEMS = (
    {
        "item_code": "item_1",
        "category": "结构状态",
        "item_name": "测试项目",
        "standards": {
            "A": "A级标准",
            "B": "B级标准",
            "C": "C级标准",
            "D": "D级标准",
        },
    },
)


class EvaluationSectionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_default_grades_remain_abcd(
        self,
    ):
        section = EvaluationSection(
            title="分项评价",
            evaluation_items=(TEST_ITEMS),
        )

        self.assertEqual(
            section.grade_options,
            (
                "A",
                "B",
                "C",
                "D",
            ),
        )

        self.assertEqual(
            tuple(section.grade_buttons["item_1"].keys()),
            (
                "A",
                "B",
                "C",
                "D",
            ),
        )

        section.deleteLater()

    def test_three_level_grades_are_supported(
        self,
    ):
        section = EvaluationSection(
            title="分项评价",
            evaluation_items=(TEST_ITEMS),
            grade_options=(
                "A",
                "B",
                "C",
            ),
        )

        self.assertEqual(
            section.grade_options,
            (
                "A",
                "B",
                "C",
            ),
        )

        self.assertEqual(
            tuple(section.grade_buttons["item_1"].keys()),
            (
                "A",
                "B",
                "C",
            ),
        )

        self.assertNotIn(
            "D",
            section.grade_buttons["item_1"],
        )

        section.deleteLater()

    def test_collect_results_uses_configured_grades(
        self,
    ):
        section = EvaluationSection(
            title="分项评价",
            evaluation_items=(TEST_ITEMS),
            grade_options=(
                "A",
                "B",
                "C",
            ),
        )

        section.grade_buttons["item_1"]["B"].setChecked(True)

        results = section.collect_results()

        self.assertEqual(
            len(results),
            1,
        )

        self.assertEqual(
            results[0]["grade"],
            "B",
        )

        section.deleteLater()

    def test_load_results_uses_configured_grades(
        self,
    ):
        section = EvaluationSection(
            title="分项评价",
            evaluation_items=(TEST_ITEMS),
            grade_options=(
                "A",
                "B",
                "C",
            ),
        )

        section.load_results(
            [
                {
                    "item_code": ("item_1"),
                    "grade": "C",
                }
            ]
        )

        self.assertTrue(section.grade_buttons["item_1"]["C"].isChecked())

        section.deleteLater()

    def test_unconfigured_grade_is_ignored_on_load(
        self,
    ):
        section = EvaluationSection(
            title="分项评价",
            evaluation_items=(TEST_ITEMS),
            grade_options=(
                "A",
                "B",
                "C",
            ),
        )

        section.load_results(
            [
                {
                    "item_code": ("item_1"),
                    "grade": "D",
                }
            ]
        )

        self.assertEqual(
            section.collect_results(),
            [],
        )

        section.deleteLater()

    def test_empty_grade_options_are_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "评价等级不能为空",
        ):
            EvaluationSection(
                title="分项评价",
                evaluation_items=(TEST_ITEMS),
                grade_options=(),
            )

    def test_duplicate_grade_options_are_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "评价等级不能重复",
        ):
            EvaluationSection(
                title="分项评价",
                evaluation_items=(TEST_ITEMS),
                grade_options=(
                    "A",
                    "B",
                    "B",
                ),
            )


if __name__ == "__main__":
    unittest.main()
