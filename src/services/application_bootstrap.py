from __future__ import annotations

from database import (
    create_initial_forms,
    init_database,
)
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

    return {
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
