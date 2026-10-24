from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_builder_module():
    path = PROJECT_ROOT / "build_update_package.py"
    spec = importlib.util.spec_from_file_location(
        "v121_update_builder",
        path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "无法加载 build_update_package.py"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V121UpdatePackageBuilderTestCase(
    unittest.TestCase,
):
    def _package(self, root):
        module = load_builder_module()
        source = root / "full"
        (source / "_internal").mkdir(parents=True)
        (source / "templates").mkdir()
        (source / "YindaSurveySystem.exe").write_bytes(b"new-program")
        (source / "_internal/new.bin").write_bytes(b"new-runtime")
        (source / "RELEASE_INFO.txt").write_text("Version=V1.2.2\n", encoding="utf-8")
        result = module.build_update_package(source, release_root=root / "packages")
        self.assertEqual(Path(result["zip_path"]).name, "YindaSurveySystem_V1.2.1_to_V1.2.2_Update.zip")
        return module, Path(result["update_dir"])

    def _install(self, root, version="1.2.1"):
        install = root / "install"
        (install / "_internal").mkdir(parents=True)
        (install / "local_data").mkdir()
        (install / "YindaSurveySystem.exe").write_bytes(b"old-program")
        (install / "_internal/old.bin").write_bytes(b"old-runtime")
        (install / "local_data/keep.txt").write_bytes(b"preserve-test-data")
        (install / "RELEASE_INFO.txt").write_text(f"Version=V{version}\n", encoding="utf-8")
        return install

    def _run_updater(self, package, install):
        # Targets are exclusively beneath this test's TemporaryDirectory.
        self.assertEqual(package.parents[1], install.parent)
        environment = os.environ.copy()
        # pwsh-hosted test runners can export an incompatible PSModulePath to PS5.
        environment["PSModulePath"] = str(
            Path(environment.get("SYSTEMROOT", r"C:\Windows"))
            / "System32/WindowsPowerShell/v1.0/Modules"
        )
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(package / "update_v1_2_2.ps1"), "-TargetDir", str(install)],
            capture_output=True, timeout=60, env=environment,
        )

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "Windows updater")
    def test_updater_preserves_data_and_replaces_complete_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, package = self._package(root)
            install = self._install(root)
            result = self._run_updater(package, install)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((install / "YindaSurveySystem.exe").read_bytes(), b"new-program")
            self.assertFalse((install / "_internal/old.bin").exists())
            self.assertEqual((install / "local_data/keep.txt").read_bytes(), b"preserve-test-data")
            backups = list((install / "upgrade_backups").glob("V1.2.1_to_V1.2.2_*/local_data/keep.txt"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), b"preserve-test-data")
            self.assertTrue(list((install / "upgrade_backups").rglob("UPDATE_COMPLETED.txt")))

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "Windows updater")
    def test_updater_rejects_corrupt_payload_before_touching_installation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, package = self._package(root)
            install = self._install(root)
            (package / "update_payload/YindaSurveySystem.exe").write_bytes(b"corrupt")
            result = self._run_updater(package, install)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("升级包文件校验失败", result.stdout.decode("utf-8", errors="replace"))
            self.assertEqual((install / "YindaSurveySystem.exe").read_bytes(), b"old-program")
            self.assertFalse((install / "upgrade_backups").exists())

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "Windows updater")
    def test_updater_rejects_wrong_origin_version(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, package = self._package(root)
            install = self._install(root, version="1.2.0")
            result = self._run_updater(package, install)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("仅支持 V1.2.1 -> V1.2.2", result.stdout.decode("utf-8", errors="replace"))
            self.assertFalse((install / "upgrade_backups").exists())
            self.assertEqual((install / "YindaSurveySystem.exe").read_bytes(), b"old-program")

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "Windows updater")
    def test_updater_rolls_back_program_when_target_version_check_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            module, package = self._package(root)
            install = self._install(root)
            payload = package / "update_payload"
            (payload / "RELEASE_INFO.txt").write_text("Version=V0.0.0\n", encoding="utf-8")
            module.write_manifest(payload, package / "UPDATE_MANIFEST.sha256")
            result = self._run_updater(package, install)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("正在回滚程序文件", result.stdout.decode("utf-8", errors="replace"))
            self.assertEqual((install / "YindaSurveySystem.exe").read_bytes(), b"old-program")
            self.assertEqual((install / "_internal/old.bin").read_bytes(), b"old-runtime")
            self.assertFalse((install / "_internal/new.bin").exists())
            self.assertEqual((install / "local_data/keep.txt").read_bytes(), b"preserve-test-data")

    def test_ui_patch_introduces_no_database_migration_requirement(self):
        module = load_builder_module()
        self.assertNotIn("pre_v1_2_2_upgrade", module.POWERSHELL_UPDATER)
        bootstrap = (PROJECT_ROOT / "src/services/application_bootstrap.py").read_text(encoding="utf-8")
        self.assertNotIn("v1_2_2", bootstrap)
        self.assertIn("历史", module.UPGRADE_NOTE)

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
            'BASE_VERSION = "1.2.1"',
            'TARGET_VERSION = "1.2.2"',
            "SafeFullPayloadUpdater",
            "UPDATE_MANIFEST.sha256",
            "Get-FileHash",
            "local_data",
            "upgrade_backups",
            "program_rollback",
            "Get-Process",
            '$currentVersion -ne "1.2.1"',
            '$newVersion -ne "1.2.2"',
            "Restore-ProgramFiles",
            "update_v1_2_2.ps1",
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
                "Version=V1.2.2\nStage=正式版\n",
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
                    / "升级到V1.2.2.bat"
                ).exists()
            )
            self.assertTrue(
                (
                    update_dir
                    / "update_v1_2_2.ps1"
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
                "Version=V1.2.2\n",
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
