from __future__ import annotations

from database import (
    create_initial_forms,
    init_database,
)
from services.official_master_data import (
    seed_official_master_data,
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
    - 甲方后续人工修改的名称、管理单位、备注等会保留。
    """

    init_database()
    create_initial_forms()

    master_data_result = (
        seed_official_master_data()
    )

    return {
        "official_master_data": (
            master_data_result
        ),
    }
