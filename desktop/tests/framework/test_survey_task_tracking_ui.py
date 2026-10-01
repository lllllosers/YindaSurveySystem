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

        key = node.args[0]
        value = node.args[1]

        if not (
            isinstance(key, ast.Constant)
            and key.value == property_name
        ):
            continue

        if (
            isinstance(value, ast.Constant)
            and value.value == property_value
        ):
            return True

    return False


class SurveyTaskTrackingUiContractTestCase(
    unittest.TestCase,
):
    def _source(self):
        return (
            PROJECT_ROOT
            / "src/pages/survey_task_page.py"
        ).read_text(encoding="utf-8")

    def test_task_page_has_issued_task_history_section(self):
        source = self._source()

        self.assertIn(
            '"四、已分发任务"',
            source,
        )

        self.assertTrue(
            _has_set_property(
                source,
                target="history_group",
                property_name="workflowCard",
                property_value=True,
            )
        )

        self.assertIn(
            "list_survey_task_tracking",
            source,
        )

    def test_task_history_has_office_filter_and_status_columns(self):
        source = self._source()

        self.assertIn(
            '"全部管理单位"',
            source,
        )

        self.assertTrue(
            _has_set_property(
                source,
                target="self.task_history_office_combo",
                property_name="uiWidthRole",
                property_value="filter",
            )
        )

        for label in (
            "分发时间",
            "基层处",
            "管理单位",
            "任务名称",
            "分管范围",
            "已回收记录",
            "回收状态",
        ):
            self.assertIn(
                f'"{label}"',
                source,
            )

    def test_successful_task_export_refreshes_tracking_history(self):
        source = self._source()

        export_start = source.index(
            "    def export_task_package(self):"
        )
        inspect_start = source.index(
            "    def inspect_existing_package(self):",
            export_start,
        )
        block = source[
            export_start:inspect_start
        ]

        self.assertIn(
            "self.refresh_task_history()",
            block,
        )


if __name__ == "__main__":
    unittest.main()
