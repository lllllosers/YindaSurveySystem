import gc
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


import database

from services import database_backup


class DatabaseBackupTestCase(unittest.TestCase):
    """
    数据库备份与恢复自动测试。

    使用独立临时数据库，
    不接触正式数据库。
    """

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()

        self.temp_root = Path(self.temp_directory.name)

        self.temp_data_dir = self.temp_root / "local_data"

        self.temp_db_path = self.temp_data_dir / "yinda_survey.db"

        self.temp_backup_dir = self.temp_data_dir / "backups"

        # =========================
        # 保存原路径
        # =========================

        self.original_database_data_dir = database.DATA_DIR

        self.original_database_db_path = database.DB_PATH

        self.original_backup_data_dir = database_backup.DATA_DIR

        self.original_backup_db_path = database_backup.DB_PATH

        self.original_backup_dir = database_backup.BACKUP_DIR

        # =========================
        # 切到测试环境
        # =========================

        database.DATA_DIR = self.temp_data_dir

        database.DB_PATH = self.temp_db_path

        database_backup.DATA_DIR = self.temp_data_dir

        database_backup.DB_PATH = self.temp_db_path

        database_backup.BACKUP_DIR = self.temp_backup_dir

        database.init_database()
        database.create_initial_forms()

    def tearDown(self):
        database.DATA_DIR = self.original_database_data_dir

        database.DB_PATH = self.original_database_db_path

        database_backup.DATA_DIR = self.original_backup_data_dir

        database_backup.DB_PATH = self.original_backup_db_path

        database_backup.BACKUP_DIR = self.original_backup_dir

        gc.collect()
        time.sleep(0.05)

        self.temp_directory.cleanup()

    def test_backup_and_restore(
        self,
    ):
        # =========================
        # 1. 建立第一版数据
        # =========================

        database.create_project(
            name="恢复前原始项目",
            short_name="原始",
        )

        # =========================
        # 2. 创建备份
        # =========================

        backup_path = database_backup.create_database_backup(
            reason="test",
            skip_if_unchanged=False,
        )

        self.assertIsNotNone(backup_path)

        assert backup_path is not None

        self.assertTrue(backup_path.exists())

        database_backup.validate_database_file(backup_path)

        # =========================
        # 3. 修改正式测试数据库
        # =========================

        database.create_project(
            name="备份之后新增项目",
            short_name="新增",
        )

        projects = database.get_projects()

        self.assertEqual(
            len(projects),
            2,
        )

        # =========================
        # 4. 恢复旧备份
        # =========================

        result = database_backup.restore_database_backup(backup_path)

        self.assertEqual(
            Path(result["restored_from"]),
            backup_path,
        )

        # 恢复前必须自动生成安全快照。
        safety_backup = result["safety_backup"]

        self.assertIsNotNone(safety_backup)

        assert safety_backup is not None

        self.assertTrue(safety_backup.exists())

        # =========================
        # 5. 验证恢复结果
        # =========================

        projects = database.get_projects()

        self.assertEqual(
            len(projects),
            1,
        )

        self.assertEqual(
            projects[0]["name"],
            "恢复前原始项目",
        )

        database_backup.validate_database_file(database.DB_PATH)


if __name__ == "__main__":
    unittest.main()
