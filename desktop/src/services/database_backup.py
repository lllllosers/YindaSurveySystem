from datetime import datetime
from pathlib import Path
import os
import sqlite3

from database import DATA_DIR, DB_PATH

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

    使用 SQLite 官方 backup API，
    避免直接复制正在使用中的数据库文件。

    返回：
        Path -> 成功创建的备份文件
        None -> 无需备份
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

    # =========================
    # 1. 创建备份
    # =========================

    try:
        source_connection = sqlite3.connect(DB_PATH)

        backup_connection = sqlite3.connect(backup_path)

        source_connection.backup(backup_connection)

        backup_connection.commit()

    except Exception:
        # 先关闭连接，再尝试删除失败文件。
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
    # 2. 确认备份文件真的生成
    # =========================

    if not backup_path.exists():
        raise RuntimeError("SQLite 备份操作结束后未生成备份文件。")

    if backup_path.stat().st_size <= 0:
        if backup_path.exists():
            try:
                backup_path.unlink()
            except OSError:
                pass

        raise RuntimeError("生成的数据库备份文件为空。")

    # =========================
    # 3. 完整性检查
    # =========================

    try:
        validate_database_file(backup_path)

    except Exception:
        # 只有完整性检查真正失败时，
        # 才删除刚生成的无效备份。
        if backup_path.exists():
            try:
                backup_path.unlink()
            except OSError:
                pass

        raise

    # =========================
    # 4. 清理旧备份
    # =========================

    _cleanup_old_backups()

    return backup_path


def get_database_backups():
    """
    获取现有数据库备份。

    返回顺序：
    最新 -> 最旧
    """

    return _get_backup_files()


def validate_database_file(
    database_path,
):
    """
    对指定 SQLite 数据库执行完整性快速检查。

    检查通过返回 True，
    检查失败直接抛出异常。
    """

    database_path = Path(database_path)

    if not database_path.exists():
        raise FileNotFoundError(f"数据库文件不存在：{database_path}")

    if database_path.stat().st_size <= 0:
        raise ValueError("数据库文件为空，无法使用。")

    connection = None

    try:
        connection = sqlite3.connect(database_path)

        result = connection.execute("PRAGMA quick_check;").fetchone()

    except sqlite3.DatabaseError as error:
        raise ValueError(
            "文件不是有效的 SQLite 数据库，" "或者数据库已经损坏。"
        ) from error

    finally:
        if connection is not None:
            connection.close()

    if result is None or result[0] != "ok":
        raise ValueError("SQLite 数据库完整性检查失败。")

    return True


def restore_database_backup(
    backup_path,
):
    """
    从指定自动备份恢复正式数据库。

    恢复流程：
    1. 验证备份文件；
    2. 当前正式数据库存在时，
       先生成 pre_restore 安全备份；
    3. 将待恢复数据库复制到临时恢复文件；
    4. 再次执行完整性检查；
    5. 原子替换正式数据库；
    6. 对恢复后的正式数据库再次检查。

    注意：
    调用本函数时主程序必须已经完全关闭。
    """

    backup_path = Path(backup_path).resolve()

    backup_directory = BACKUP_DIR.resolve()

    # 只允许恢复系统自己的备份目录中的数据库。
    if backup_path.parent != backup_directory:
        raise ValueError("只能恢复 backups 目录中的" "系统数据库备份。")

    validate_database_file(backup_path)

    # =========================
    # 恢复前保护当前正式数据库
    # =========================

    safety_backup = None

    if DB_PATH.exists() and DB_PATH.stat().st_size > 0:
        safety_backup = create_database_backup(
            reason="pre_restore",
            skip_if_unchanged=False,
        )

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_restore_path = DATA_DIR / "yinda_survey_restore_pending.db"

    if temp_restore_path.exists():
        temp_restore_path.unlink()

    source_connection = None
    restore_connection = None

    try:
        source_connection = sqlite3.connect(backup_path)

        restore_connection = sqlite3.connect(temp_restore_path)

        source_connection.backup(restore_connection)

        restore_connection.commit()

    except Exception:
        if temp_restore_path.exists():
            try:
                temp_restore_path.unlink()
            except OSError:
                pass

        raise

    finally:
        if restore_connection is not None:
            restore_connection.close()

        if source_connection is not None:
            source_connection.close()

    # 临时恢复文件必须完整。
    validate_database_file(temp_restore_path)

    # 如果以后开启 WAL，
    # 恢复时不能保留旧数据库遗留的 WAL/SHM。
    for suffix in (
        "-wal",
        "-shm",
    ):
        auxiliary_path = Path(f"{DB_PATH}{suffix}")

        if auxiliary_path.exists():
            try:
                auxiliary_path.unlink()
            except OSError as error:
                raise RuntimeError(
                    "数据库辅助文件仍被占用。" "请确认主程序已经完全关闭。"
                ) from error

    # 使用原子替换正式数据库。
    os.replace(
        temp_restore_path,
        DB_PATH,
    )

    # 恢复完成后最后检查一次。
    validate_database_file(DB_PATH)

    return {
        "restored_from": (backup_path),
        "safety_backup": (safety_backup),
    }
