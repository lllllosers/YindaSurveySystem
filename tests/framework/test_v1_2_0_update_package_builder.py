from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_builder_module():
    path = PROJECT_ROOT / "build_update_package.py"
    spec = importlib.util.spec_from_file_location(
        "v120_update_builder",
        path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "无法加载 build_update_package.py"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V120UpdatePackageBuilderTestCase(
    unittest.TestCase,
):
    def test_update_builder_has_safety_contract(
        self,
    ):
        source = (
            PROJECT_ROOT
            / "build_update_package.py"
        ).read_text(
            encoding="utf-8"
        )

        for expected in (
            'BASE_VERSION = "1.1.1"',
            'TARGET_VERSION = "1.2.0"',
            "SafeFullPayloadUpdater",
            "UPDATE_MANIFEST.sha256",
            "Get-FileHash",
            "local_data",
            "upgrade_backups",
            "program_rollback",
            "Get-Process",
            '$currentVersion -ne "1.1.1"',
            '$newVersion -ne "1.2.0"',
            "Restore-ProgramFiles",
            "update_v1_2_0.ps1",
        ):
            self.assertIn(
                expected,
                source,
            )

    def test_builder_creates_verified_update_package(
        self,
    ):
        module = load_builder_module()

        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            source_release = temp_root / "full_release"

            (source_release / "_internal").mkdir(
                parents=True,
            )
            (
                source_release
                / "templates"
                / "excel"
            ).mkdir(
                parents=True,
            )

            (
                source_release
                / "YindaSurveySystem.exe"
            ).write_bytes(
                b"fake-exe"
            )
            (
                source_release
                / "_internal"
                / "runtime.bin"
            ).write_bytes(
                b"runtime"
            )
            (
                source_release
                / "templates"
                / "excel"
                / "template.xlsx"
            ).write_bytes(
                b"template"
            )
            (
                source_release
                / "RELEASE_INFO.txt"
            ).write_text(
                "Version=V1.2.0\nStage=正式版\n",
                encoding="utf-8",
            )

            release_root = temp_root / "release"

            result = module.build_update_package(
                source_release,
                release_root=release_root,
            )

            update_dir = Path(result["update_dir"])
            zip_path = Path(result["zip_path"])

            self.assertTrue(update_dir.exists())
            self.assertTrue(zip_path.exists())
            self.assertTrue(
                (
                    update_dir
                    / "升级到V1.2.0.bat"
                ).exists()
            )
            self.assertTrue(
                (
                    update_dir
                    / "update_v1_2_0.ps1"
                ).exists()
            )
            self.assertTrue(
                (
                    update_dir
                    / "UPDATE_MANIFEST.sha256"
                ).exists()
            )
            self.assertTrue(
                (
                    update_dir
                    / "update_payload"
                    / "YindaSurveySystem.exe"
                ).exists()
            )
            self.assertFalse(
                (
                    update_dir
                    / "update_payload"
                    / "local_data"
                ).exists()
            )

            module.verify_zip(zip_path)

    def test_source_release_with_local_data_is_rejected(
        self,
    ):
        module = load_builder_module()

        with tempfile.TemporaryDirectory() as temp:
            source_release = Path(temp) / "full_release"
            (source_release / "_internal").mkdir(
                parents=True,
            )
            (source_release / "templates").mkdir(
                parents=True,
            )
            (source_release / "local_data").mkdir(
                parents=True,
            )

            (
                source_release
                / "YindaSurveySystem.exe"
            ).write_bytes(
                b"fake-exe"
            )
            (
                source_release
                / "RELEASE_INFO.txt"
            ).write_text(
                "Version=V1.2.0\n",
                encoding="utf-8",
            )
            (
                source_release
                / "local_data"
                / "yinda_survey.db"
            ).write_bytes(
                b"do-not-package"
            )

            with self.assertRaises(RuntimeError):
                module.validate_source_release(
                    source_release
                )


if __name__ == "__main__":
    unittest.main()
