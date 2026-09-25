import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUERY_PAGE = PROJECT_ROOT / "src" / "pages" / "data_query_page.py"


def _target_name(node):
    if isinstance(node, ast.Name):
        return node.id

    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
    ):
        return f"{node.value.id}.{node.attr}"

    return None


def _source_owner_name(node):
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        left = _source_owner_name(node.value)
        if left:
            return f"{left}.{node.attr}"

    return None


class DataQueryActionOrderContractTestCase(unittest.TestCase):
    def test_query_action_order(self):
        source = QUERY_PAGE.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(QUERY_PAGE))

        init_nodes = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "init_ui"
        ]
        self.assertEqual(1, len(init_nodes))
        init_ui = init_nodes[0]

        # Resolve the actual local variable names from the visible button text.
        # This keeps the test stable if the implementation uses names such as
        # open_button / open_record_button / open_full_record_button.
        button_vars = {}

        for node in ast.walk(init_ui):
            if not isinstance(node, ast.Assign):
                continue

            if len(node.targets) != 1:
                continue

            target = _target_name(node.targets[0])
            if target is None:
                continue

            value = node.value
            if not isinstance(value, ast.Call):
                continue

            func = value.func
            call_name = None

            if isinstance(func, ast.Name):
                call_name = func.id
            elif isinstance(func, ast.Attribute):
                call_name = func.attr

            if call_name != "QPushButton":
                continue

            if not value.args:
                continue

            label = value.args[0]

            if (
                isinstance(label, ast.Constant)
                and isinstance(label.value, str)
            ):
                button_vars[label.value] = target

        expected_labels = (
            "导出查询结果",
            "打开完整调查表",
            "刷新数据",
            "重置",
            "查询",
        )

        for label in expected_labels:
            self.assertIn(
                label,
                button_vars,
                f"缺少按钮：{label}",
            )

        # Read the final filter_action_row calls in source order.
        action_calls = []

        for node in ast.walk(init_ui):
            if not isinstance(node, ast.Expr):
                continue

            call = node.value

            if not isinstance(call, ast.Call):
                continue

            func = call.func

            if not isinstance(func, ast.Attribute):
                continue

            if _source_owner_name(func.value) != "filter_action_row":
                continue

            if func.attr == "addStretch":
                action_calls.append(
                    (
                        node.lineno,
                        "__stretch__",
                    )
                )
                continue

            if func.attr != "addWidget":
                continue

            if len(call.args) != 1:
                continue

            arg_name = _target_name(call.args[0])

            if arg_name:
                action_calls.append(
                    (
                        node.lineno,
                        arg_name,
                    )
                )

        action_order = [
            name
            for _line, name in sorted(action_calls)
        ]

        expected_order = [
            button_vars["导出查询结果"],
            button_vars["打开完整调查表"],
            "__stretch__",
            button_vars["刷新数据"],
            button_vars["重置"],
            button_vars["查询"],
        ]

        self.assertEqual(
            expected_order,
            action_order,
        )

        # Query remains the primary action; opening a record is secondary.
        self.assertIn(
            f'{button_vars["查询"]}.setProperty("uiRole", "primary")',
            source,
        )
        self.assertIn(
            f'{button_vars["打开完整调查表"]}.setProperty('
            '"uiRole", "secondary")',
            source,
        )


if __name__ == "__main__":
    unittest.main()
