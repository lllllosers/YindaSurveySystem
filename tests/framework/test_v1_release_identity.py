import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _constant(
    source: str,
    name: str,
):
    tree = ast.parse(source)

    for node in tree.body:
        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        if (
            len(node.targets) == 1
            and isinstance(
                node.targets[0],
                ast.Name,
            )
            and node.targets[0].id
            == name
            and isinstance(
                node.value,
                ast.Constant,
            )
        ):
            return node.value.value

    raise AssertionError(
        f"Constant not found: {name}"
    )


class V1ReleaseIdentityContractTestCase(
    unittest.TestCase,
):
    def test_runtime_identity_is_v1_final(self):
        source = (
            PROJECT_ROOT
            / "src/version.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertEqual(
            _constant(
                source,
                "APP_NAME",
            ),
            "引大入秦工程现状调查采集系统",
        )
        self.assertEqual(
            _constant(
                source,
                "APP_VERSION",
            ),
            "1.1.0",
        )
        self.assertEqual(
            _constant(
                source,
                "APP_STAGE",
            ),
            "正式版",
        )

    def test_current_readme_uses_v1_identity(self):
        source = (
            PROJECT_ROOT
            / "README.md"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "# 引大入秦工程现状调查采集系统",
            source,
        )
        self.assertIn(
            "**V1.1.0 正式版**",
            source,
        )
        self.assertNotIn(
            "尚未进入正式 `1.0.0` 发布版本",
            source,
        )

    def test_runtime_source_has_no_stale_development_placeholder(self):
        main_source = (
            PROJECT_ROOT
            / "src/main.py"
        ).read_text(
            encoding="utf-8"
        )
        restore_source = (
            PROJECT_ROOT
            / "src/restore_database.py"
        ).read_text(
            encoding="utf-8"
        )
        result_page_source = (
            PROJECT_ROOT
            / "src/pages/result_receive_page.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "该模块将在后续开发步骤中逐步实现",
            main_source,
        )
        self.assertNotIn(
            "引大灌区调查数据采集系统",
            restore_source,
        )
        self.assertNotIn(
            "任务下发时",
            result_page_source,
        )


if __name__ == "__main__":
    unittest.main()
