import ast
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from services.survey_result_import_preflight import (
    SurveyResultImportPreflight,
    SurveyResultPreflightIssue,
)


class V111UserFacingCopyTestCase(unittest.TestCase):
    def _visible_strings(self, path):
        tree = ast.parse(
            path.read_text(
                encoding="utf-8"
            )
        )

        docstring_nodes = set()

        for owner in ast.walk(tree):
            if not isinstance(
                owner,
                (
                    ast.Module,
                    ast.ClassDef,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                continue

            body = getattr(
                owner,
                "body",
                (),
            )

            if not body:
                continue

            first = body[0]

            if (
                isinstance(first, ast.Expr)
                and isinstance(
                    first.value,
                    ast.Constant,
                )
                and isinstance(
                    first.value.value,
                    str,
                )
            ):
                docstring_nodes.add(
                    id(first.value)
                )

        values = []

        for node in ast.walk(tree):
            if not (
                isinstance(
                    node,
                    ast.Constant,
                )
                and isinstance(
                    node.value,
                    str,
                )
            ):
                continue

            if id(node) in docstring_nodes:
                continue

            if not any(
                "\u4e00" <= char <= "\u9fff"
                for char in node.value
            ):
                continue

            values.append(
                node.value
            )

        return values

    def test_pages_do_not_show_developer_jargon(self):
        banned = (
            "Registry",
            "revision",
            "CanalManagementScope",
            "稳定 UID",
            "工作区",
            "预检",
            "事务",
            "物理删除",
            "正式主数据",
            "阻断性",
            "SurveyRecord",
            "package_uid",
            "result_uid",
            "托管",
        )
        failures = []
        for path in sorted((SRC_DIR / "pages").rglob("*.py")):
            for value in self._visible_strings(path):
                for token in banned:
                    if token in value:
                        failures.append(
                            (
                                str(path.relative_to(PROJECT_ROOT)),
                                token,
                                value,
                            )
                        )
        self.assertEqual(
            failures,
            [],
            "\n".join(
                ["仍发现面向用户的技术化文案："]
                + [
                    f"- {path}: {token}: {value!r}"
                    for path, token, value in failures
                ]
            ),
        )

    def test_result_check_has_business_facing_text(self):
        report = SurveyResultImportPreflight(
            package_path=Path("demo.ydresult"),
            package_uid="package-internal",
            result_uid="result-internal",
            project_uid="project-internal",
            survey_batch_uid="batch-internal",
            new_assets=1,
            existing_assets=0,
            new_records=1,
            existing_records=0,
            new_inspections=2,
            existing_inspections=0,
            new_media=0,
            existing_media=0,
            issues=(
                SurveyResultPreflightIssue(
                    severity="info",
                    code="SOURCE_TASK_PROVENANCE_VERIFIED",
                    message="成果来源任务已核验，调查记录均在任务授权范围内。",
                    entity_uid="internal-uid",
                ),
            ),
        )
        text = report.format_user_text()
        self.assertIn("成果来源任务已核验", text)
        self.assertNotIn("SOURCE_TASK_PROVENANCE_VERIFIED", text)
        self.assertNotIn("internal-uid", text)
        self.assertNotIn("package-internal", text)

    def test_copy_standard_is_updated(self):
        text = (
            PROJECT_ROOT / "docs" / "07_术语与界面文案规范.md"
        ).read_text(encoding="utf-8")
        for expected in (
            "检查成果包",
            "内部技术代码不直接展示",
            "需要用户采取行动",
            "当前任务",
        ):
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
