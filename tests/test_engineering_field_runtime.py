import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from PySide6.QtGui import (
    QDoubleValidator,
    QIntValidator,
)

from PySide6.QtWidgets import (
    QApplication,
)

from forms.engineering.models import (
    FieldDefinition,
)

from pages.components.engineering_field_runtime import (
    create_engineering_field_runtime,
)


class EngineeringFieldRuntimeTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    # =========================================================
    # text
    # =========================================================

    def test_text_field(
        self,
    ):
        runtime = create_engineering_field_runtime(
            FieldDefinition(
                key="name",
                label="名称",
                input_type="text",
                placeholder="填写名称",
            )
        )

        self.assertEqual(
            runtime.widget.placeholderText(),
            "填写名称",
        )

        runtime.widget.setText("  测试涵洞  ")

        self.assertEqual(
            runtime.get_value(),
            "测试涵洞",
        )

        runtime.set_value("测试渡槽")

        self.assertEqual(
            runtime.widget.text(),
            "测试渡槽",
        )

        runtime.clear()

        self.assertTrue(runtime.is_blank())

        runtime.widget.deleteLater()

    # =========================================================
    # decimal
    # =========================================================

    def test_decimal_field(
        self,
    ):
        runtime = create_engineering_field_runtime(
            FieldDefinition(
                key="design_flow",
                label="设计流量",
                input_type="decimal",
            )
        )

        self.assertIsInstance(
            runtime.widget.validator(),
            QDoubleValidator,
        )

        runtime.widget.setText("6.5")

        self.assertEqual(
            runtime.get_value(),
            6.5,
        )

        runtime.widget.deleteLater()

    # =========================================================
    # signed decimal
    # =========================================================

    def test_signed_decimal_field(
        self,
    ):
        runtime = create_engineering_field_runtime(
            FieldDefinition(
                key=("bottom_elevation"),
                label="底部高程",
                input_type=("signed_decimal"),
            )
        )

        runtime.widget.setText("-3.5")

        self.assertEqual(
            runtime.get_value(),
            -3.5,
        )

        runtime.widget.deleteLater()

    # =========================================================
    # integer
    # =========================================================

    def test_integer_field(
        self,
    ):
        runtime = create_engineering_field_runtime(
            FieldDefinition(
                key="span_count",
                label="跨数",
                input_type="integer",
                maximum=999,
            )
        )

        validator = runtime.widget.validator()

        self.assertIsInstance(
            validator,
            QIntValidator,
        )

        self.assertEqual(
            validator.top(),
            999,
        )

        runtime.widget.setText("12")

        self.assertEqual(
            runtime.get_value(),
            12,
        )

        runtime.widget.deleteLater()

    # =========================================================
    # month
    # =========================================================

    def test_month_field(
        self,
    ):
        runtime = create_engineering_field_runtime(
            FieldDefinition(
                key="build_date",
                label="建成年月",
                input_type="month",
            )
        )

        runtime.widget.setText("2010-06")

        self.assertEqual(
            runtime.get_value(),
            "2010-06",
        )

        runtime.widget.deleteLater()

    def test_invalid_month_is_rejected(
        self,
    ):
        runtime = create_engineering_field_runtime(
            FieldDefinition(
                key="build_date",
                label="建成年月",
                input_type="month",
            )
        )

        runtime.widget.setText("2010-13")

        with self.assertRaisesRegex(
            ValueError,
            "YYYY-MM",
        ):
            runtime.get_value()

        runtime.widget.deleteLater()

    # =========================================================
    # stake
    # =========================================================

    def test_stake_field_normalizes_value(
        self,
    ):
        runtime = create_engineering_field_runtime(
            FieldDefinition(
                key="stake",
                label="桩号",
                input_type="stake",
            )
        )

        runtime.widget.setText("K12+350")

        self.assertEqual(
            runtime.get_value(),
            "CH12+350",
        )

        self.assertEqual(
            runtime.get_stake_parts(),
            (
                "CH12+350",
                12350.0,
            ),
        )

        runtime.widget.deleteLater()

    def test_non_stake_cannot_get_stake_parts(
        self,
    ):
        runtime = create_engineering_field_runtime(
            FieldDefinition(
                key="name",
                label="名称",
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "stake",
        ):
            runtime.get_stake_parts()

        runtime.widget.deleteLater()

    # =========================================================
    # None / 回填 / dirty
    # =========================================================

    def test_none_value_clears_widget(
        self,
    ):
        runtime = create_engineering_field_runtime(
            FieldDefinition(
                key="name",
                label="名称",
            )
        )

        runtime.set_value("测试")

        runtime.set_value(None)

        self.assertTrue(runtime.is_blank())

        runtime.widget.deleteLater()

    def test_programmatic_set_does_not_mark_dirty(
        self,
    ):
        runtime = create_engineering_field_runtime(
            FieldDefinition(
                key="name",
                label="名称",
            )
        )

        called = []

        runtime.connect_dirty(lambda *args: (called.append(True)))

        # setText() 只触发 textChanged，
        # 不触发 textEdited。
        runtime.set_value("程序回填")

        self.assertEqual(
            called,
            [],
        )

        # 模拟用户编辑信号。
        runtime.widget.textEdited.emit("用户修改")

        self.assertEqual(
            called,
            [True],
        )

        runtime.widget.deleteLater()

    # =========================================================
    # 不支持类型
    # =========================================================

    def test_unknown_type_is_rejected(
        self,
    ):
        definition = FieldDefinition(
            key="unknown",
            label="未知字段",
            input_type="unknown",
        )

        with self.assertRaisesRegex(
            ValueError,
            "暂不支持",
        ):
            create_engineering_field_runtime(definition)


if __name__ == "__main__":
    unittest.main()
