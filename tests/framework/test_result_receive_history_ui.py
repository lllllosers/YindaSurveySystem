import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _dotted_name(node):
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        left = _dotted_name(node.value)
        if left:
            return f"{left}.{node.attr}"

    return None


def _has_set_property(
    source: str,
    *,
    target: str,
    property_name: str,
    property_value,
) -> bool:
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "setProperty"
        ):
            continue

        if _dotted_name(func.value) != target:
            continue

        if len(node.args) < 2:
            continue

        key_node = node.args[0]
        value_node = node.args[1]

        if not (
            isinstance(key_node, ast.Constant)
            and key_node.value == property_name
        ):
            continue

        if (
            isinstance(value_node, ast.Constant)
            and value_node.value == property_value
        ):
            return True

    return False


class ResultReceiveHistoryUiContractTestCase(
    unittest.TestCase,
):
    def _source(self):
        return (
            PROJECT_ROOT
            / "src/pages/result_receive_page.py"
        ).read_text(encoding="utf-8")

    def test_result_receive_page_has_receive_and_history_sections(self):
        source = self._source()

        self.assertIn(
            '"一、接收新成果"',
            source,
        )
        self.assertIn(
            '"二、已接收成果"',
            source,
        )

        self.assertTrue(
            _has_set_property(
                source,
                target="receive_group",
                property_name="workflowCard",
                property_value=True,
            )
        )
        self.assertTrue(
            _has_set_property(
                source,
                target="history_group",
                property_name="workflowCard",
                property_value=True,
            )
        )

    def test_history_has_office_filter_and_expected_columns(self):
        source = self._source()

        self.assertIn(
            '"全部管理单位"',
            source,
        )

        self.assertTrue(
            _has_set_property(
                source,
                target="self.history_office_combo",
                property_name="uiWidthRole",
                property_value="filter",
            )
        )

        for label in (
            "接收时间",
            "管理单位",
            "成果名称",
            "调查记录",
            "工程",
            "分项评价",
            "影像",
            "接收状态",
        ):
            self.assertIn(
                f'"{label}"',
                source,
            )

    def test_history_refreshes_after_successful_import(self):
        source = self._source()

        self.assertIn(
            "self.refresh_history()",
            source,
        )
        self.assertIn(
            "self.result_imported.emit(",
            source,
        )

    def test_page_uses_scroll_container_to_avoid_expanding_main_window(self):
        source = self._source()

        self.assertIn(
            "QScrollArea",
            source,
        )
        self.assertIn(
            "self.scroll_area.setWidgetResizable(",
            source,
        )
        self.assertIn(
            "self.scroll_content = QWidget()",
            source,
        )
        self.assertIn(
            "layout = QVBoxLayout(",
            source,
        )
        self.assertIn(
            "self.scroll_content",
            source,
        )


if __name__ == "__main__":
    unittest.main()
