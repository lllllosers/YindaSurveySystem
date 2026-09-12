from datetime import datetime
from pathlib import Path
import sqlite3

from database import (
    DATA_DIR,
    DB_PATH,
)

BACKUP_DIR = DATA_DIR / "backups"

MAX_BACKUPS = 20


def _get_backup_files():
    """
    获取已有数据库备份，
    按修改时间从新到旧排列。
    """

    if not BACKUP_DIR.exists():
        return []

    return sorted(
        BACKUP_DIR.glob("yinda_survey_*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _database_changed_since_last_backup():
    """
    判断正式数据库自最近一次备份后
    是否发生过变化。
    """

    if not DB_PATH.exists():
        return False

    backup_files = _get_backup_files()

    if not backup_files:
        return True

    latest_backup = backup_files[0]

    return DB_PATH.stat().st_mtime > latest_backup.stat().st_mtime


def _cleanup_old_backups():
    """
    只保留最近 MAX_BACKUPS 份备份。
    """

    backup_files = _get_backup_files()

    for old_backup in backup_files[MAX_BACKUPS:]:
        try:
            old_backup.unlink()
        except OSError:
            # 清理旧备份失败不影响当前备份。
            pass


def create_database_backup(
    reason="auto",
    skip_if_unchanged=True,
):
    """
    创建 SQLite 数据库备份。

    参数：
        reason:
            startup / exit / manual 等，
            仅用于备份文件名识别。

        skip_if_unchanged:
            True 时，如果数据库自最近一次备份后
            没有变化，则不重复创建备份。

    返回：
        成功创建：Path
        无需备份：None
    """

    if not DB_PATH.exists():
        return None

    if DB_PATH.stat().st_size <= 0:
        return None

    if skip_if_unchanged and not _database_changed_since_last_backup():
        return None

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    safe_reason = "".join(
        char for char in str(reason) if char.isalnum() or char in ("-", "_")
    )

    if not safe_reason:
        safe_reason = "auto"

    backup_path = BACKUP_DIR / (f"yinda_survey_" f"{timestamp}_" f"{safe_reason}.db")

    source_connection = None
    backup_connection = None

    try:
        source_connection = sqlite3.connect(DB_PATH)

        backup_connection = sqlite3.connect(backup_path)

        # SQLite 官方在线备份机制。
        source_connection.backup(backup_connection)

        backup_connection.commit()

    except Exception:
        if backup_connection is not None:
            backup_connection.close()
            backup_connection = None

        if source_connection is not None:
            source_connection.close()
            source_connection = None

        if backup_path.exists():
            try:
                backup_path.unlink()
            except OSError:
                pass

        raise

    finally:
        if backup_connection is not None:
            backup_connection.close()

        if source_connection is not None:
            source_connection.close()

    # =========================
    # 备份完整性检查
    # =========================

    try:
        with sqlite3.connect(backup_path) as check_connection:

            result = check_connection.execute("PRAGMA quick_check;").fetchone()

            if result is None or result[0] != "ok":
                raise RuntimeError("数据库备份完整性检查失败。")

    except Exception:
        if backup_path.exists():
            try:
                backup_path.unlink()
            except OSError:
                pass

        raise

    _cleanup_old_backups()

    return backup_path
