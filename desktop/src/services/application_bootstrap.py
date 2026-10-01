from __future__ import annotations

from datetime import datetime

import database as database_module
from database import (
    create_initial_forms,
    init_database,
)
from services import database_backup as database_backup_module
from services.official_master_data import (
    seed_official_master_data,
)
from services.master_identity import (
    synchronize_official_master_identities,
)
from services.canal_management_scope import (
    ensure_canal_management_scope_schema,
)
from services.official_canal_management_scope import (
    seed_official_canal_management_scopes,
)
from services.survey_task_issue_history import (
    ensure_survey_task_issue_history_schema,
)
from services.survey_task_record_scope import (
    ensure_survey_task_record_scope_schema,
)
from services.survey_result_import import (
    ensure_survey_result_import_schema,
)


_V120_UPGRADE_BACKUP_REASON = "pre_v1_2_0_upgrade"
_V120_UPGRADE_MARKER_NAME = ".v1_2_0_upgrade_backup_complete"


def _v120_upgrade_marker_path():
    return (
        database_module.DATA_DIR
        / _V120_UPGRADE_MARKER_NAME
    )


def prepare_v120_upgrade_backup():
    # V1.2.0 首次启动安全保护：
    # - 新数据库不创建空备份；
    # - 既有数据库在任何迁移前创建一次强制备份；
    # - 只有完整初始化成功后才写完成标记。

    marker_path = (
        _v120_upgrade_marker_path()
    )

    if marker_path.exists():
        return {
            "required": False,
            "backup_created": False,
            "backup_path": None,
            "marker_path": marker_path,
            "state": "already_completed",
        }

    database_path = (
        database_module.DB_PATH
    )

    if (
        not database_path.exists()
        or database_path.stat().st_size <= 0
    ):
        return {
            "required": False,
            "backup_created": False,
            "backup_path": None,
            "marker_path": marker_path,
            "state": "fresh_database",
        }

    original_data_dir = (
        database_backup_module.DATA_DIR
    )
    original_db_path = (
        database_backup_module.DB_PATH
    )
    original_backup_dir = (
        database_backup_module.BACKUP_DIR
    )

    try:
        # 测试会动态替换 database.DATA_DIR / DB_PATH。
        # database_backup 历史上持有自己的模块级路径，
        # 因此仅在本次调用期间临时同步，finally 后恢复。
        database_backup_module.DATA_DIR = (
            database_module.DATA_DIR
        )
        database_backup_module.DB_PATH = (
            database_module.DB_PATH
        )
        database_backup_module.BACKUP_DIR = (
            database_module.DATA_DIR
            / "backups"
        )

        backup_path = (
            database_backup_module
            .create_database_backup(
                reason=(
                    _V120_UPGRADE_BACKUP_REASON
                ),
                skip_if_unchanged=False,
            )
        )

    finally:
        database_backup_module.DATA_DIR = (
            original_data_dir
        )
        database_backup_module.DB_PATH = (
            original_db_path
        )
        database_backup_module.BACKUP_DIR = (
            original_backup_dir
        )

    if backup_path is None:
        raise RuntimeError(
            "V1.2.0 升级前数据库备份未生成，"
            "已停止启动以避免无备份迁移。"
        )

    return {
        "required": True,
        "backup_created": True,
        "backup_path": backup_path,
        "marker_path": marker_path,
        "state": "backup_created",
    }


def mark_v120_upgrade_backup_complete():
    # 仅在完整应用数据库初始化成功后写入一次性完成标记。
    marker_path = (
        _v120_upgrade_marker_path()
    )

    marker_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = marker_path.with_name(
        marker_path.name + ".tmp"
    )

    temp_path.write_text(
        (
            "V1.2.0 upgrade bootstrap completed\n"
            f"{datetime.now().isoformat(timespec='seconds')}\n"
        ),
        encoding="utf-8",
    )

    temp_path.replace(
        marker_path
    )

    return marker_path


def initialize_application_database():
    """
    初始化应用运行所需的全部本地数据库基础设施。

    顺序：
    1. 建立 / 升级数据库结构；
    2. 建立附表定义；
    3. 首次数据库自动写入甲方正式组织机构和渠系主数据。

    official_master_data 的种子本身具有版本记录：
    - 新数据库首次启动会自动写入；
    - 已成功写入过的数据库不会重复覆盖；
    - 甲方后续人工修改的组织/渠系名称、备注等会保留；
    - 渠道管理关系由 CanalManagementScope 独立维护。
    """

    v120_upgrade_backup_result = (
        prepare_v120_upgrade_backup()
    )

    init_database()
    create_initial_forms()

    master_data_result = (
        seed_official_master_data()
    )

    master_identity_result = (
        synchronize_official_master_identities()
    )

    canal_management_scope_result = (
        ensure_canal_management_scope_schema()
    )

    official_canal_management_scope_result = (
        seed_official_canal_management_scopes()
    )

    task_issue_history_result = (
        ensure_survey_task_issue_history_schema()
    )

    task_record_scope_result = (
        ensure_survey_task_record_scope_schema()
    )

    result_import_result = (
        ensure_survey_result_import_schema()
    )

    mark_v120_upgrade_backup_complete()

    return {
        "v1_2_0_upgrade_backup": (
            v120_upgrade_backup_result
        ),
        "official_master_data": (
            master_data_result
        ),
        "official_master_identity": (
            master_identity_result
        ),
        "canal_management_scope": (
            canal_management_scope_result
        ),
        "official_canal_management_scope": (
            official_canal_management_scope_result
        ),
        "survey_task_issue_history": (
            task_issue_history_result
        ),
        "survey_task_record_scope": (
            task_record_scope_result
        ),
        "survey_result_import": (
            result_import_result
        ),
    }
