from __future__ import annotations

import gc
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


import database

from services.application_bootstrap import (
    initialize_application_database,
)


class V120UpgradeBackupTestCase(
    unittest.TestCase,
):
    def setUp(self):
        self.temp_directory = (
            tempfile.TemporaryDirectory()
        )

        self.temp_root = Path(
            self.temp_directory.name
        )
        self.temp_data_dir = (
            self.temp_root / "local_data"
        )
        self.temp_db_path = (
            self.temp_data_dir
            / "yinda_survey.db"
        )

        self.original_data_dir = (
            database.DATA_DIR
        )
        self.original_db_path = (
            database.DB_PATH
        )

        database.DATA_DIR = (
            self.temp_data_dir
        )
        database.DB_PATH = (
            self.temp_db_path
        )

    def tearDown(self):
        database.DATA_DIR = (
            self.original_data_dir
        )
        database.DB_PATH = (
            self.original_db_path
        )

        gc.collect()
        time.sleep(0.05)

        self.temp_directory.cleanup()

    def test_existing_database_is_backed_up_once_before_v120_bootstrap(
        self,
    ):
        # 模拟已经存在的旧版本数据库。
        # 直接初始化数据库，不经过 application bootstrap，
        # 因此还没有 V1.2.0 完成标记。
        database.init_database()
        database.create_initial_forms()

        database.create_project(
            name="升级前保留项目",
            short_name="升级前",
        )

        marker_path = (
            self.temp_data_dir
            / ".v1_2_0_upgrade_backup_complete"
        )

        self.assertFalse(
            marker_path.exists()
        )

        result = (
            initialize_application_database()
        )

        upgrade = result[
            "v1_2_0_upgrade_backup"
        ]

        self.assertTrue(
            upgrade["required"]
        )
        self.assertTrue(
            upgrade["backup_created"]
        )

        backup_path = Path(
            upgrade["backup_path"]
        )

        self.assertTrue(
            backup_path.exists()
        )
        self.assertIn(
            "pre_v1_2_0_upgrade",
            backup_path.name,
        )

        # 备份必须真实包含升级前已有数据。
        connection = sqlite3.connect(
            backup_path
        )

        try:
            project = connection.execute(
                "SELECT name FROM projects WHERE name = ?",
                ("升级前保留项目",),
            ).fetchone()
        finally:
            connection.close()

        self.assertIsNotNone(
            project
        )

        # 只有完整 bootstrap 成功后才会留下完成标记。
        self.assertTrue(
            marker_path.exists()
        )

        backup_dir = (
            self.temp_data_dir
            / "backups"
        )

        backups_before = sorted(
            backup_dir.glob(
                "*pre_v1_2_0_upgrade.db"
            )
        )

        self.assertEqual(
            len(backups_before),
            1,
        )

        # 第二次启动不能重复创建升级备份。
        second_result = (
            initialize_application_database()
        )

        second_upgrade = second_result[
            "v1_2_0_upgrade_backup"
        ]

        self.assertFalse(
            second_upgrade["required"]
        )
        self.assertFalse(
            second_upgrade["backup_created"]
        )
        self.assertEqual(
            second_upgrade["state"],
            "already_completed",
        )

        backups_after = sorted(
            backup_dir.glob(
                "*pre_v1_2_0_upgrade.db"
            )
        )

        self.assertEqual(
            backups_after,
            backups_before,
        )

    def test_fresh_database_does_not_create_empty_upgrade_backup(
        self,
    ):
        self.assertFalse(
            self.temp_db_path.exists()
        )

        result = (
            initialize_application_database()
        )

        upgrade = result[
            "v1_2_0_upgrade_backup"
        ]

        self.assertFalse(
            upgrade["required"]
        )
        self.assertFalse(
            upgrade["backup_created"]
        )
        self.assertEqual(
            upgrade["state"],
            "fresh_database",
        )

        self.assertTrue(
            self.temp_db_path.exists()
        )

        marker_path = (
            self.temp_data_dir
            / ".v1_2_0_upgrade_backup_complete"
        )

        self.assertTrue(
            marker_path.exists()
        )

        backup_dir = (
            self.temp_data_dir
            / "backups"
        )

        if backup_dir.exists():
            self.assertEqual(
                list(
                    backup_dir.glob(
                        "*pre_v1_2_0_upgrade.db"
                    )
                ),
                [],
            )


if __name__ == "__main__":
    unittest.main()
