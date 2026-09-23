import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class V1ReleaseBuilderContractTestCase(
    unittest.TestCase,
):
    def test_production_builder_exists_and_test_builder_is_removed(self):
        self.assertTrue(
            (
                PROJECT_ROOT
                / "build_release.py"
            ).exists()
        )
        self.assertTrue(
            (
                PROJECT_ROOT
                / "build_release.bat"
            ).exists()
        )
        self.assertFalse(
            (
                PROJECT_ROOT
                / "build_test_release.py"
            ).exists()
        )
        self.assertFalse(
            (
                PROJECT_ROOT
                / "build_test_release.bat"
            ).exists()
        )

    def test_builder_has_final_release_contract(self):
        source = (
            PROJECT_ROOT
            / "build_release.py"
        ).read_text(
            encoding="utf-8"
        )

        ast.parse(source)

        for expected in (
            'EXPECTED_VERSION = "1.2.0"',
            'EXPECTED_STAGE = "正式版"',
            'EXPECTED_BRANCH = "release/v1.2.0"',
            "require_clean=True",
            "run_tests.py",
            "PyInstaller",
            "verify_release_tree",
            "verify_zip",
            "calculate_sha256",
            "RELEASE_INFO.txt",
            "V1.2.0_发布说明.md",
            "V1.2.0_生产验收记录.md",
            "local_data",
        ):
            self.assertIn(
                expected,
                source,
            )

        for stale in (
            "Test Release Builder",
            "阶段性测试发布包",
            'f"V{version}_test"',
            "甲方测试反馈模板",
        ):
            self.assertNotIn(
                stale,
                source,
            )

    def test_pyinstaller_version_is_pinned(self):
        requirements = (
            PROJECT_ROOT
            / "requirements.txt"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "PyInstaller==6.22.2",
            requirements,
        )


if __name__ == "__main__":
    unittest.main()
