from datetime import datetime
from pathlib import Path
import json
import sqlite3
import sys


def get_app_root():
    """
    获取程序运行根目录。

    开发环境：
        项目根目录

    PyInstaller 打包环境：
        exe 文件所在目录
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


# 程序运行根目录
PROJECT_ROOT = get_app_root()

# 本地数据目录
DATA_DIR = PROJECT_ROOT / "local_data"

# SQLite 数据库文件
DB_PATH = DATA_DIR / "yinda_survey.db"


class AutoCloseConnection(sqlite3.Connection):
    """
    SQLite 连接。

    在 with 代码块结束时：
    1. 先执行 sqlite3.Connection 原有的提交/回滚逻辑；
    2. 再明确关闭连接。

    这样可以避免 Windows 下数据库文件
    因连接句柄未及时释放而无法删除或替换。
    """

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        try:
            return super().__exit__(
                exc_type,
                exc_value,
                traceback,
            )
        finally:
            self.close()


def get_connection():
    """
    获取 SQLite 数据库连接。

    推荐始终使用：

        with get_connection() as connection:
            ...

    离开 with 后连接会自动关闭。
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DB_PATH,
        factory=AutoCloseConnection,
    )

    connection.row_factory = sqlite3.Row

    # 启用外键约束
    connection.execute("PRAGMA foreign_keys = ON;")

    return connection


def init_database():
    """
    初始化数据库。
    当前第一阶段只建立：
    1. 项目表 projects
    2. 调查批次表 survey_batches
    """

    with get_connection() as connection:
        connection.executescript("""

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                name TEXT NOT NULL,
                short_name TEXT,
                description TEXT,

                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'inactive')),

                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                updated_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime'))
            );


            CREATE TABLE IF NOT EXISTS survey_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                project_id INTEGER NOT NULL,

                batch_name TEXT NOT NULL,
                batch_code TEXT NOT NULL,

                start_date TEXT,
                end_date TEXT,

                description TEXT,

                status TEXT NOT NULL DEFAULT 'draft'
                    CHECK (
                        status IN (
                            'draft',
                            'active',
                            'completed',
                            'archived'
                        )
                    ),

                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                updated_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                UNIQUE (project_id, batch_code),

                FOREIGN KEY (project_id)
                    REFERENCES projects(id)
            );


            CREATE TABLE IF NOT EXISTS organization_units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                parent_id INTEGER,

                name TEXT NOT NULL,

                unit_type TEXT NOT NULL
                    CHECK (
                        unit_type IN (
                            'department',
                            'water_office'
                        )
                    ),

                business_code TEXT,

                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (
                        status IN (
                            'active',
                            'inactive'
                        )
                    ),

                description TEXT,

                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                updated_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                FOREIGN KEY (parent_id)
                    REFERENCES organization_units(id)
            );


            CREATE TABLE IF NOT EXISTS canal_units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                parent_id INTEGER,

                name TEXT NOT NULL,

                canal_level TEXT NOT NULL
                    CHECK (
                        canal_level IN (
                            '01',
                            '02',
                            '03',
                            '04'
                        )
                    ),

                organization_unit_id INTEGER,

                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (
                        status IN (
                            'active',
                            'inactive'
                        )
                    ),

                description TEXT,

                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                updated_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                FOREIGN KEY (parent_id)
                    REFERENCES canal_units(id),

                FOREIGN KEY (organization_unit_id)
                    REFERENCES organization_units(id)
            );


            CREATE TABLE IF NOT EXISTS form_definitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                form_code TEXT NOT NULL UNIQUE,
                form_number TEXT NOT NULL,
                form_name TEXT NOT NULL,

                series TEXT NOT NULL
                    CHECK (series IN ('series_1', 'series_2')),

                record_type TEXT NOT NULL
                    CHECK (
                        record_type IN (
                            'comprehensive',
                            'engineering'
                        )
                    ),

                asset_type TEXT,

                is_enabled INTEGER NOT NULL DEFAULT 1
                    CHECK (is_enabled IN (0, 1)),

                sort_order INTEGER NOT NULL DEFAULT 0,

                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime'))
            );


            CREATE TABLE IF NOT EXISTS form_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                form_definition_id INTEGER NOT NULL,

                version_code TEXT NOT NULL,
                version_name TEXT,

                effective_date TEXT,

                schema_json TEXT NOT NULL DEFAULT '{}',

                is_current INTEGER NOT NULL DEFAULT 1
                    CHECK (is_current IN (0, 1)),

                notes TEXT,

                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                UNIQUE (
                    form_definition_id,
                    version_code
                ),

                FOREIGN KEY (form_definition_id)
                    REFERENCES form_definitions(id)
            );

            
            CREATE TABLE IF NOT EXISTS engineering_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                project_id INTEGER NOT NULL,

                asset_name TEXT NOT NULL,
                asset_type TEXT NOT NULL,

                organization_unit_id INTEGER NOT NULL,
                canal_unit_id INTEGER NOT NULL,

                business_code TEXT NOT NULL,
                code_scheme_version TEXT NOT NULL DEFAULT 'V1',

                single_stake_text TEXT,
                single_stake_value REAL,

                start_stake_text TEXT,
                start_stake_value REAL,

                end_stake_text TEXT,
                end_stake_value REAL,

                first_survey_batch_id INTEGER,

                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (
                        status IN (
                            'active',
                            'inactive',
                            'retired'
                        )
                    ),

                notes TEXT,

                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                updated_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                UNIQUE (
                    project_id,
                    business_code
                ),

                FOREIGN KEY (project_id)
                    REFERENCES projects(id),

                FOREIGN KEY (organization_unit_id)
                    REFERENCES organization_units(id),

                FOREIGN KEY (canal_unit_id)
                    REFERENCES canal_units(id),

                FOREIGN KEY (first_survey_batch_id)
                    REFERENCES survey_batches(id)
            );


            CREATE TABLE IF NOT EXISTS survey_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                project_id INTEGER NOT NULL,
                survey_batch_id INTEGER NOT NULL,
                form_version_id INTEGER NOT NULL,

                record_type TEXT NOT NULL
                    CHECK (
                        record_type IN (
                            'comprehensive',
                            'engineering'
                        )
                    ),

                organization_unit_id INTEGER,
                canal_unit_id INTEGER,
                engineering_asset_id INTEGER,

                business_code TEXT,

                survey_date TEXT,

                overall_grade TEXT
                    CHECK (
                        overall_grade IS NULL
                        OR overall_grade IN (
                            'A',
                            'B',
                            'C',
                            'D'
                        )
                    ),

                survey_comment TEXT,

                record_status TEXT NOT NULL DEFAULT 'draft'
                    CHECK (
                        record_status IN (
                            'draft',
                            'completed',
                            'void'
                        )
                    ),

                record_data_json TEXT NOT NULL DEFAULT '{}',

                void_reason TEXT,

                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                updated_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                FOREIGN KEY (project_id)
                    REFERENCES projects(id),

                FOREIGN KEY (survey_batch_id)
                    REFERENCES survey_batches(id),

                FOREIGN KEY (form_version_id)
                    REFERENCES form_versions(id),

                FOREIGN KEY (organization_unit_id)
                    REFERENCES organization_units(id),

                FOREIGN KEY (canal_unit_id)
                    REFERENCES canal_units(id),

                FOREIGN KEY (engineering_asset_id)
                    REFERENCES engineering_assets(id)
            );


            CREATE TABLE IF NOT EXISTS inspection_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                survey_record_id INTEGER NOT NULL,

                item_code TEXT NOT NULL,
                category TEXT NOT NULL,
                item_name TEXT NOT NULL,

                grade TEXT
                    CHECK (
                        grade IS NULL
                        OR grade IN (
                            'A',
                            'B',
                            'C',
                            'D'
                        )
                    ),

                description TEXT,
                remark TEXT,

                updated_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                UNIQUE (
                    survey_record_id,
                    item_code
                ),

                FOREIGN KEY (survey_record_id)
                    REFERENCES survey_records(id)
                    ON DELETE CASCADE
            );
            """)


def get_projects():
    """
    获取全部项目。
    """

    with get_connection() as connection:
        return connection.execute("""
            SELECT
                id,
                name,
                short_name,
                description,
                status,
                created_at,
                updated_at
            FROM projects
            ORDER BY id
            """).fetchall()


def create_project(
    name,
    short_name=None,
    description=None,
):
    """
    新增项目。

    如果系统当前没有启用项目，
    新建的第一个项目自动设为 active。

    如果已经存在当前项目，
    新项目先保存为 inactive，
    由用户明确切换。
    """

    name = str(name or "").strip()
    short_name = str(short_name or "").strip()
    description = str(description or "").strip()

    if not name:
        raise ValueError("项目名称不能为空。")

    with get_connection() as connection:
        duplicate = connection.execute(
            """
            SELECT id
            FROM projects
            WHERE name = ?
            LIMIT 1
            """,
            (name,),
        ).fetchone()

        if duplicate is not None:
            raise ValueError("已经存在同名项目。")

        active_project = connection.execute("""
            SELECT id
            FROM projects
            WHERE status = 'active'
            LIMIT 1
            """).fetchone()

        status = "active" if active_project is None else "inactive"

        cursor = connection.execute(
            """
            INSERT INTO projects (
                name,
                short_name,
                description,
                status
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                name,
                short_name or None,
                description or None,
                status,
            ),
        )

        return {
            "project_id": cursor.lastrowid,
            "status": status,
        }


def set_active_project(
    project_id,
):
    """
    将指定项目设为当前启用项目。

    当前版本只允许一个 active 项目。
    """

    with get_connection() as connection:
        project = connection.execute(
            """
            SELECT id
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        ).fetchone()

        if project is None:
            raise ValueError("没有找到指定项目。")

        connection.execute(
            """
            UPDATE projects
            SET
                status = 'inactive',
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE status = 'active'
            AND id != ?
            """,
            (project_id,),
        )

        connection.execute(
            """
            UPDATE projects
            SET
                status = 'active',
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (project_id,),
        )


def get_survey_batches(
    project_id,
):
    """
    获取指定项目下的全部调查批次。
    """

    with get_connection() as connection:
        return connection.execute(
            """
            SELECT
                id,
                project_id,
                batch_name,
                batch_code,
                start_date,
                end_date,
                description,
                status,
                created_at,
                updated_at
            FROM survey_batches
            WHERE project_id = ?
            ORDER BY id DESC
            """,
            (project_id,),
        ).fetchall()


def create_survey_batch(
    project_id,
    batch_name,
    batch_code,
    start_date=None,
    end_date=None,
    description=None,
):
    """
    新增调查批次。

    当前项目如果尚无 active 调查批次，
    新批次自动设为 active。

    否则新批次先保存为 draft。
    """

    batch_name = str(batch_name or "").strip()

    batch_code = str(batch_code or "").strip()

    start_date = str(start_date or "").strip()

    end_date = str(end_date or "").strip()

    description = str(description or "").strip()

    if not batch_name:
        raise ValueError("调查批次名称不能为空。")

    if not batch_code:
        raise ValueError("调查批次代码不能为空。")

    if start_date:
        try:
            datetime.strptime(
                start_date,
                "%Y-%m-%d",
            )
        except ValueError as error:
            raise ValueError("开始日期必须为 YYYY-MM-DD。") from error

    if end_date:
        try:
            datetime.strptime(
                end_date,
                "%Y-%m-%d",
            )
        except ValueError as error:
            raise ValueError("结束日期必须为 YYYY-MM-DD。") from error

    if start_date and end_date and start_date > end_date:
        raise ValueError("结束日期不能早于开始日期。")

    with get_connection() as connection:
        project = connection.execute(
            """
            SELECT
                id,
                status
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        ).fetchone()

        if project is None:
            raise ValueError("没有找到所属项目。")

        duplicate = connection.execute(
            """
            SELECT id
            FROM survey_batches
            WHERE project_id = ?
            AND batch_code = ?
            LIMIT 1
            """,
            (
                project_id,
                batch_code,
            ),
        ).fetchone()

        if duplicate is not None:
            raise ValueError("当前项目下已经存在相同批次代码。")

        active_batch = connection.execute(
            """
            SELECT id
            FROM survey_batches
            WHERE project_id = ?
            AND status = 'active'
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()

        if project["status"] == "active" and active_batch is None:
            status = "active"
        else:
            status = "draft"

        cursor = connection.execute(
            """
            INSERT INTO survey_batches (
                project_id,
                batch_name,
                batch_code,
                start_date,
                end_date,
                description,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                batch_name,
                batch_code,
                start_date or None,
                end_date or None,
                description or None,
                status,
            ),
        )

        return {
            "batch_id": cursor.lastrowid,
            "status": status,
        }


def set_active_survey_batch(
    batch_id,
):
    """
    将指定调查批次设为当前调查批次。

    同时：
    1. 该批次所属项目设为当前项目；
    2. 同项目其它 active 批次退回 draft；
    3. 指定批次设为 active。
    """

    with get_connection() as connection:
        batch = connection.execute(
            """
            SELECT
                id,
                project_id
            FROM survey_batches
            WHERE id = ?
            """,
            (batch_id,),
        ).fetchone()

        if batch is None:
            raise ValueError("没有找到指定调查批次。")

        project_id = batch["project_id"]

        # 当前项目同步切换
        connection.execute(
            """
            UPDATE projects
            SET
                status = 'inactive',
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE status = 'active'
            AND id != ?
            """,
            (project_id,),
        )

        connection.execute(
            """
            UPDATE projects
            SET
                status = 'active',
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (project_id,),
        )

        # 同一项目只保留一个当前调查批次
        connection.execute(
            """
            UPDATE survey_batches
            SET
                status = 'draft',
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE project_id = ?
            AND status = 'active'
            AND id != ?
            """,
            (
                project_id,
                batch_id,
            ),
        )

        connection.execute(
            """
            UPDATE survey_batches
            SET
                status = 'active',
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (batch_id,),
        )


def create_demo_data():
    """
    创建开发测试用的示例项目和调查批次。

    注意：
    本函数仅允许由开发辅助脚本调用，
    正式程序 main.py 不得自动调用。

    重复执行不会重复创建相同测试数据。
    """

    with get_connection() as connection:

        project = connection.execute(
            """
            SELECT id
            FROM projects
            WHERE name = ?
            """,
            ("引大入秦灌区现状调查",),
        ).fetchone()

        if project is None:
            cursor = connection.execute(
                """
                INSERT INTO projects (
                    name,
                    short_name,
                    description,
                    status
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    "引大入秦灌区现状调查",
                    "引大调查",
                    "系统开发阶段示例项目",
                    "active",
                ),
            )

            project_id = cursor.lastrowid
        else:
            project_id = project["id"]

        batch = connection.execute(
            """
            SELECT id
            FROM survey_batches
            WHERE project_id = ?
            AND batch_code = ?
            """,
            (
                project_id,
                "2026_FULL",
            ),
        ).fetchone()

        if batch is None:
            connection.execute(
                """
                INSERT INTO survey_batches (
                    project_id,
                    batch_name,
                    batch_code,
                    start_date,
                    end_date,
                    description,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    "2026年度全面调查",
                    "2026_FULL",
                    "2026-09-01",
                    "2026-12-31",
                    "开发测试用调查批次",
                    "active",
                ),
            )


def create_initial_forms():
    """
    初始化系统内置调查表定义。

    调查表定义属于系统元数据，
    正式运行环境也需要自动初始化。

    当前已经建立：
    - 附表2.1 防渗衬砌渠道
    - 附表2.2 水闸
    - 附表2.3 渡槽（座槽）
    - 附表2.4 倒虹吸
    - 附表2.5 隧洞
    """

    forms = [
        {
            "form_code": "form_2_1",
            "form_number": "2.1",
            "form_name": "防渗衬砌渠道渠段工程状况调查表",
            "series": "series_2",
            "record_type": "engineering",
            "asset_type": "lined_channel_section",
            "sort_order": 201,
        },
        {
            "form_code": "form_2_2",
            "form_number": "2.2",
            "form_name": "水闸工程状况调查表",
            "series": "series_2",
            "record_type": "engineering",
            "asset_type": "sluice_gate",
            "sort_order": 202,
        },
        {
            "form_code": "form_2_3",
            "form_number": "2.3",
            "form_name": "渡槽（座槽）工程状况调查表",
            "series": "series_2",
            "record_type": "engineering",
            "asset_type": "aqueduct",
            "sort_order": 203,
        },
        {
            "form_code": "form_2_4",
            "form_number": "2.4",
            "form_name": "倒虹吸工程状况调查表",
            "series": "series_2",
            "record_type": "engineering",
            "asset_type": "inverted_siphon",
            "sort_order": 204,
        },
        {
            "form_code": "form_2_5",
            "form_number": "2.5",
            "form_name": "隧洞工程状况调查表",
            "series": "series_2",
            "record_type": "engineering",
            "asset_type": "tunnel",
            "sort_order": 205,
        },
    ]

    with get_connection() as connection:
        for form in forms:
            existing = connection.execute(
                """
                SELECT id
                FROM form_definitions
                WHERE form_code = ?
                """,
                (form["form_code"],),
            ).fetchone()

            if existing is None:
                cursor = connection.execute(
                    """
                    INSERT INTO form_definitions (
                        form_code,
                        form_number,
                        form_name,
                        series,
                        record_type,
                        asset_type,
                        sort_order
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        form["form_code"],
                        form["form_number"],
                        form["form_name"],
                        form["series"],
                        form["record_type"],
                        form["asset_type"],
                        form["sort_order"],
                    ),
                )

                form_definition_id = cursor.lastrowid
            else:
                form_definition_id = existing["id"]

            version = connection.execute(
                """
                SELECT id
                FROM form_versions
                WHERE form_definition_id = ?
                AND version_code = 'V1'
                """,
                (form_definition_id,),
            ).fetchone()

            if version is None:
                connection.execute(
                    """
                    INSERT INTO form_versions (
                        form_definition_id,
                        version_code,
                        version_name,
                        effective_date,
                        schema_json,
                        is_current
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        form_definition_id,
                        "V1",
                        "2026版",
                        "2026-09-01",
                        "{}",
                        1,
                    ),
                )


def get_departments():
    """
    获取所有基层处。
    """
    with get_connection() as connection:
        return connection.execute("""
            SELECT *
            FROM organization_units
            WHERE unit_type = 'department'
            ORDER BY id
            """).fetchall()


def get_water_offices(department_id=None):
    """
    获取水管所。

    如果传入 department_id，
    则只获取该基层处下面的水管所。
    """
    with get_connection() as connection:
        if department_id is None:
            return connection.execute("""
                SELECT *
                FROM organization_units
                WHERE unit_type = 'water_office'
                ORDER BY parent_id, id
                """).fetchall()

        return connection.execute(
            """
            SELECT *
            FROM organization_units
            WHERE unit_type = 'water_office'
              AND parent_id = ?
            ORDER BY id
            """,
            (department_id,),
        ).fetchall()


def create_organization_unit(
    name,
    unit_type,
    business_code=None,
    parent_id=None,
    description=None,
):
    """
    新增基层处或水管所。
    """

    if unit_type not in ("department", "water_office"):
        raise ValueError("无效的组织机构类型。")

    if not name or not name.strip():
        raise ValueError("组织机构名称不能为空。")

    # 水管所必须属于一个基层处
    if unit_type == "water_office" and parent_id is None:
        raise ValueError("水管所必须选择所属基层处。")

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO organization_units (
                parent_id,
                name,
                unit_type,
                business_code,
                description
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                parent_id,
                name.strip(),
                unit_type,
                business_code.strip() if business_code else None,
                description.strip() if description else None,
            ),
        )

        return cursor.lastrowid


def get_organization_unit(
    unit_id,
):
    """
    获取单个组织机构。
    """

    with get_connection() as connection:
        return connection.execute(
            """
            SELECT *
            FROM organization_units
            WHERE id = ?
            """,
            (unit_id,),
        ).fetchone()


def get_organization_unit_usage(
    unit_id,
):
    """
    获取组织机构引用情况。

    基层处的业务引用同时包括
    其直属水管所产生的工程和调查记录。
    """

    with get_connection() as connection:
        unit = connection.execute(
            """
            SELECT
                id,
                unit_type
            FROM organization_units
            WHERE id = ?
            """,
            (unit_id,),
        ).fetchone()

        if unit is None:
            raise ValueError("没有找到指定组织机构。")

        child_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM organization_units
            WHERE parent_id = ?
            """,
            (unit_id,),
        ).fetchone()[0]

        canal_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM canal_units
            WHERE organization_unit_id = ?
            """,
            (unit_id,),
        ).fetchone()[0]

        asset_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM engineering_assets
            WHERE organization_unit_id = ?
            """,
            (unit_id,),
        ).fetchone()[0]

        survey_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM survey_records
            WHERE organization_unit_id = ?
            """,
            (unit_id,),
        ).fetchone()[0]

        descendant_asset_count = 0
        descendant_survey_count = 0

        if unit["unit_type"] == "department":
            descendant_asset_count = connection.execute(
                """
                    SELECT COUNT(*)
                    FROM engineering_assets AS ea
                    JOIN organization_units AS ou
                        ON ea.organization_unit_id = ou.id
                    WHERE ou.parent_id = ?
                    """,
                (unit_id,),
            ).fetchone()[0]

            descendant_survey_count = connection.execute(
                """
                    SELECT COUNT(*)
                    FROM survey_records AS sr
                    JOIN organization_units AS ou
                        ON sr.organization_unit_id = ou.id
                    WHERE ou.parent_id = ?
                    """,
                (unit_id,),
            ).fetchone()[0]

        business_reference_count = (
            asset_count
            + survey_count
            + descendant_asset_count
            + descendant_survey_count
        )

        return {
            "child_count": int(child_count),
            "canal_count": int(canal_count),
            "asset_count": int(asset_count),
            "survey_count": int(survey_count),
            "descendant_asset_count": int(descendant_asset_count),
            "descendant_survey_count": int(descendant_survey_count),
            "business_reference_count": int(business_reference_count),
            "business_code_locked": (business_reference_count > 0),
            "can_delete": (
                child_count == 0
                and canal_count == 0
                and asset_count == 0
                and survey_count == 0
            ),
        }


def update_organization_unit(
    unit_id,
    name,
    business_code=None,
    parent_id=None,
    description=None,
):
    """
    修改组织机构。

    已产生工程/调查业务数据时：
    - 名称、备注仍允许修改；
    - 业务代码禁止修改；
    - 水管所所属基层处禁止修改。
    """

    name = str(name or "").strip()

    business_code = str(business_code).strip() if business_code is not None else ""

    description = str(description).strip() if description is not None else ""

    if not name:
        raise ValueError("组织机构名称不能为空。")

    current = get_organization_unit(unit_id)

    if current is None:
        raise ValueError("没有找到指定组织机构。")

    unit_type = current["unit_type"]

    if unit_type == "department":
        parent_id = None

    elif unit_type == "water_office":
        if parent_id is None:
            raise ValueError("水管所必须选择所属基层处。")

    else:
        raise ValueError("无效的组织机构类型。")

    usage = get_organization_unit_usage(unit_id)

    old_business_code = current["business_code"] or ""

    old_parent_id = current["parent_id"]

    if business_code != old_business_code and usage["business_code_locked"]:
        raise ValueError("该组织机构已经产生工程或调查数据，" "业务代码不能再修改。")

    if (
        unit_type == "water_office"
        and parent_id != old_parent_id
        and usage["business_reference_count"] > 0
    ):
        raise ValueError("该水管所已经产生工程或调查数据，" "所属基层处不能再修改。")

    with get_connection() as connection:
        if unit_type == "water_office":
            parent = connection.execute(
                """
                SELECT
                    id,
                    unit_type
                FROM organization_units
                WHERE id = ?
                """,
                (parent_id,),
            ).fetchone()

            if parent is None or parent["unit_type"] != "department":
                raise ValueError("所属基层处无效。")

        if business_code:
            if unit_type == "department":
                duplicate = connection.execute(
                    """
                    SELECT id
                    FROM organization_units
                    WHERE unit_type = 'department'
                      AND business_code = ?
                      AND id != ?
                    LIMIT 1
                    """,
                    (
                        business_code,
                        unit_id,
                    ),
                ).fetchone()

            else:
                duplicate = connection.execute(
                    """
                    SELECT id
                    FROM organization_units
                    WHERE unit_type = 'water_office'
                      AND parent_id = ?
                      AND business_code = ?
                      AND id != ?
                    LIMIT 1
                    """,
                    (
                        parent_id,
                        business_code,
                        unit_id,
                    ),
                ).fetchone()

            if duplicate is not None:
                raise ValueError("业务代码已经被其他同级机构使用。")

        connection.execute(
            """
            UPDATE organization_units
            SET
                parent_id = ?,
                name = ?,
                business_code = ?,
                description = ?,
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (
                parent_id,
                name,
                business_code or None,
                description or None,
                unit_id,
            ),
        )


def set_organization_unit_status(
    unit_id,
    status,
):
    """
    启用或停用组织机构。
    """

    if status not in (
        "active",
        "inactive",
    ):
        raise ValueError("无效的组织机构状态。")

    with get_connection() as connection:
        current = connection.execute(
            """
            SELECT id
            FROM organization_units
            WHERE id = ?
            """,
            (unit_id,),
        ).fetchone()

        if current is None:
            raise ValueError("没有找到指定组织机构。")

        connection.execute(
            """
            UPDATE organization_units
            SET
                status = ?,
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (
                status,
                unit_id,
            ),
        )


def delete_organization_unit(
    unit_id,
):
    """
    物理删除未被使用的组织机构。

    已存在下属机构、管理渠系、
    工程台账或调查记录时禁止删除。
    """

    usage = get_organization_unit_usage(unit_id)

    if not usage["can_delete"]:
        reasons = []

        if usage["child_count"]:
            reasons.append(f"下属机构 {usage['child_count']} 个")

        if usage["canal_count"]:
            reasons.append(f"管理渠系 {usage['canal_count']} 个")

        if usage["asset_count"]:
            reasons.append(f"工程对象 {usage['asset_count']} 个")

        if usage["survey_count"]:
            reasons.append(f"调查记录 {usage['survey_count']} 条")

        reason_text = "、".join(reasons)

        raise ValueError(
            "该组织机构不能物理删除，" f"当前存在：{reason_text}。" "请改为停用。"
        )

    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM organization_units
            WHERE id = ?
            """,
            (unit_id,),
        )


def get_canal_lineage(
    canal_unit_id,
):
    """
    获取某个渠系节点从根节点到当前节点的完整层级链。

    例如：
        总干渠(01)
        -> 某支渠(03)
        -> 某分支渠(04)

    返回顺序：
        上级 -> 下级
    """

    if canal_unit_id is None:
        return []

    lineage = []
    visited_ids = set()

    with get_connection() as connection:
        current_id = canal_unit_id

        while current_id is not None:

            # 防止基础资料异常形成循环引用
            if current_id in visited_ids:
                raise ValueError("渠系层级存在循环引用，" "无法确定上级渠系。")

            visited_ids.add(current_id)

            row = connection.execute(
                """
                SELECT
                    id,
                    parent_id,
                    name,
                    canal_level
                FROM canal_units
                WHERE id = ?
                """,
                (current_id,),
            ).fetchone()

            if row is None:
                break

            lineage.append(
                {
                    "id": row["id"],
                    "parent_id": row["parent_id"],
                    "name": row["name"] or "",
                    "canal_level": row["canal_level"],
                }
            )

            current_id = row["parent_id"]

    # 查询过程是 当前 -> 上级，
    # 对外返回 上级 -> 当前。
    lineage.reverse()

    return lineage


def get_canal_units():
    """
    获取全部渠系。
    """
    with get_connection() as connection:
        return connection.execute("""
            SELECT
                c.*,
                o.name AS organization_name
            FROM canal_units AS c
            LEFT JOIN organization_units AS o
                ON c.organization_unit_id = o.id
            ORDER BY c.id
            """).fetchall()


def create_canal_unit(
    name,
    canal_level,
    parent_id=None,
    organization_unit_id=None,
    description=None,
):
    """
    新增渠系。
    """

    if not name or not name.strip():
        raise ValueError("渠道名称不能为空。")

    if canal_level not in ("01", "02", "03", "04"):
        raise ValueError("无效的渠道层级。")

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO canal_units (
                parent_id,
                name,
                canal_level,
                organization_unit_id,
                description
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                parent_id,
                name.strip(),
                canal_level,
                organization_unit_id,
                description.strip() if description else None,
            ),
        )

        return cursor.lastrowid


def get_canal_unit(
    canal_unit_id,
):
    """
    获取单个渠系节点。
    """

    with get_connection() as connection:
        return connection.execute(
            """
            SELECT *
            FROM canal_units
            WHERE id = ?
            """,
            (canal_unit_id,),
        ).fetchone()


def get_canal_unit_usage(
    canal_unit_id,
):
    """
    获取渠系节点引用情况。
    """

    with get_connection() as connection:
        current = connection.execute(
            """
            SELECT id
            FROM canal_units
            WHERE id = ?
            """,
            (canal_unit_id,),
        ).fetchone()

        if current is None:
            raise ValueError("没有找到指定渠系。")

        child_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM canal_units
            WHERE parent_id = ?
            """,
            (canal_unit_id,),
        ).fetchone()[0]

        asset_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM engineering_assets
            WHERE canal_unit_id = ?
            """,
            (canal_unit_id,),
        ).fetchone()[0]

        survey_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM survey_records
            WHERE canal_unit_id = ?
            """,
            (canal_unit_id,),
        ).fetchone()[0]

        business_reference_count = asset_count + survey_count

        return {
            "child_count": int(child_count),
            "asset_count": int(asset_count),
            "survey_count": int(survey_count),
            "business_reference_count": int(business_reference_count),
            "structure_locked": (business_reference_count > 0),
            "can_delete": (child_count == 0 and asset_count == 0 and survey_count == 0),
        }


def update_canal_unit(
    canal_unit_id,
    name,
    canal_level,
    parent_id=None,
    organization_unit_id=None,
    description=None,
):
    """
    修改渠系。

    已产生工程/调查数据后：
    - 名称、备注允许修改；
    - 渠道层级、上级渠道、管理单位锁定。
    """

    name = str(name or "").strip()

    description = str(description).strip() if description is not None else ""

    if not name:
        raise ValueError("渠道名称不能为空。")

    if canal_level not in (
        "01",
        "02",
        "03",
        "04",
    ):
        raise ValueError("无效的渠道层级。")

    current = get_canal_unit(canal_unit_id)

    if current is None:
        raise ValueError("没有找到指定渠系。")

    if parent_id == canal_unit_id:
        raise ValueError("渠道不能把自己设为上级渠道。")

    usage = get_canal_unit_usage(canal_unit_id)

    structure_changed = (
        canal_level != current["canal_level"]
        or parent_id != current["parent_id"]
        or organization_unit_id != current["organization_unit_id"]
    )

    if structure_changed and usage["structure_locked"]:
        raise ValueError(
            "该渠系已经产生工程或调查数据，"
            "渠道层级、上级渠道和管理单位"
            "不能再修改。"
        )

    with get_connection() as connection:
        # 上级渠道必须存在，
        # 同时防止形成循环引用。
        current_parent_id = parent_id
        visited_ids = set()

        while current_parent_id is not None:
            if current_parent_id == canal_unit_id:
                raise ValueError("渠系层级不能形成循环引用。")

            if current_parent_id in visited_ids:
                raise ValueError("渠系层级存在循环引用。")

            visited_ids.add(current_parent_id)

            parent = connection.execute(
                """
                SELECT
                    id,
                    parent_id
                FROM canal_units
                WHERE id = ?
                """,
                (current_parent_id,),
            ).fetchone()

            if parent is None:
                raise ValueError("上级渠道不存在。")

            current_parent_id = parent["parent_id"]

        if organization_unit_id is not None:
            organization = connection.execute(
                """
                SELECT id
                FROM organization_units
                WHERE id = ?
                """,
                (organization_unit_id,),
            ).fetchone()

            if organization is None:
                raise ValueError("管理单位不存在。")

        connection.execute(
            """
            UPDATE canal_units
            SET
                parent_id = ?,
                name = ?,
                canal_level = ?,
                organization_unit_id = ?,
                description = ?,
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (
                parent_id,
                name,
                canal_level,
                organization_unit_id,
                description or None,
                canal_unit_id,
            ),
        )


def set_canal_unit_status(
    canal_unit_id,
    status,
):
    """
    启用或停用渠系。
    """

    if status not in (
        "active",
        "inactive",
    ):
        raise ValueError("无效的渠系状态。")

    with get_connection() as connection:
        current = connection.execute(
            """
            SELECT id
            FROM canal_units
            WHERE id = ?
            """,
            (canal_unit_id,),
        ).fetchone()

        if current is None:
            raise ValueError("没有找到指定渠系。")

        connection.execute(
            """
            UPDATE canal_units
            SET
                status = ?,
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (
                status,
                canal_unit_id,
            ),
        )


def delete_canal_unit(
    canal_unit_id,
):
    """
    物理删除未被使用的渠系节点。

    存在下级渠道、工程对象或调查记录时
    禁止删除。
    """

    usage = get_canal_unit_usage(canal_unit_id)

    if not usage["can_delete"]:
        reasons = []

        if usage["child_count"]:
            reasons.append(f"下级渠道 {usage['child_count']} 个")

        if usage["asset_count"]:
            reasons.append(f"工程对象 {usage['asset_count']} 个")

        if usage["survey_count"]:
            reasons.append(f"调查记录 {usage['survey_count']} 条")

        reason_text = "、".join(reasons)

        raise ValueError(
            "该渠系不能物理删除，" f"当前存在：{reason_text}。" "请改为停用。"
        )

    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM canal_units
            WHERE id = ?
            """,
            (canal_unit_id,),
        )


def get_canal_units_for_organization(
    organization_unit_id,
):
    """
    获取某个管理单位下启用的渠系。
    """
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT *
            FROM canal_units
            WHERE organization_unit_id = ?
            AND status = 'active'
            ORDER BY id
            """,
            (organization_unit_id,),
        ).fetchall()


def get_engineering_business_codes(
    project_id,
):
    """
    获取当前项目已经使用的工程业务编号。
    """
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT business_code
            FROM engineering_assets
            WHERE project_id = ?
            ORDER BY id
            """,
            (project_id,),
        ).fetchall()

        return [row["business_code"] for row in rows if row["business_code"]]


def get_current_form_version(
    form_code,
):
    """
    根据 form_code 获取当前启用的表单版本。
    """
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT
                fv.*,
                fd.form_code,
                fd.form_number,
                fd.form_name,
                fd.asset_type
            FROM form_versions AS fv
            JOIN form_definitions AS fd
                ON fv.form_definition_id = fd.id
            WHERE fd.form_code = ?
            AND fv.is_current = 1
            ORDER BY fv.id DESC
            LIMIT 1
            """,
            (form_code,),
        ).fetchone()


def get_engineering_form_definitions():
    """
    获取当前系统已经定义的全部工程调查表。

    数据查询模块使用该函数生成
    “调查表”筛选条件。

    即使未来某个表单被停用，
    历史调查记录仍然应该允许查询，
    因此这里不只返回 is_enabled = 1。
    """

    with get_connection() as connection:
        return connection.execute("""
            SELECT
                id,
                form_code,
                form_number,
                form_name,
                asset_type,
                is_enabled,
                sort_order
            FROM form_definitions
            WHERE series = 'series_2'
              AND record_type = 'engineering'
            ORDER BY
                sort_order,
                id
            """).fetchall()


def get_engineering_survey_query_records(
    project_id,
    survey_batch_id=None,
    form_code=None,
):
    """
    获取统一工程调查查询结果。

    当前用于“数据查询”模块。

    查询范围：
    - 当前项目；
    - 可选指定调查批次；
    - 可选指定调查表；
    - 排除 void 记录。

    本函数只返回所有工程调查表都具有的公共字段，
    不返回附表2.1、2.2各自的业务专用字段。
    """

    if project_id is None:
        return []

    sql = """
        SELECT
            sr.id AS survey_record_id,
            sr.project_id,
            sr.survey_batch_id,

            sb.batch_name,
            sb.batch_code,

            fd.form_code,
            fd.form_number,
            fd.form_name,
            fd.asset_type,
            fd.sort_order,

            ea.id AS engineering_asset_id,
            ea.asset_name,

            ea.single_stake_text,
            ea.start_stake_text,
            ea.end_stake_text,

            sr.business_code,
            sr.overall_grade,
            sr.survey_date,
            sr.record_status,
            sr.updated_at,

            office.name AS office_name,
            department.name AS department_name,

            canal.name AS canal_name

        FROM survey_records AS sr

        JOIN survey_batches AS sb
            ON sr.survey_batch_id = sb.id

        JOIN form_versions AS fv
            ON sr.form_version_id = fv.id

        JOIN form_definitions AS fd
            ON fv.form_definition_id = fd.id

        LEFT JOIN engineering_assets AS ea
            ON sr.engineering_asset_id = ea.id

        LEFT JOIN organization_units AS office
            ON sr.organization_unit_id = office.id

        LEFT JOIN organization_units AS department
            ON office.parent_id = department.id

        LEFT JOIN canal_units AS canal
            ON sr.canal_unit_id = canal.id

        WHERE sr.project_id = ?
          AND sr.record_type = 'engineering'
          AND sr.record_status != 'void'
    """

    parameters = [
        project_id,
    ]

    if survey_batch_id is not None:
        sql += """
          AND sr.survey_batch_id = ?
        """

        parameters.append(survey_batch_id)

    if form_code:
        sql += """
          AND fd.form_code = ?
        """

        parameters.append(form_code)

    sql += """
        ORDER BY
            sb.id DESC,
            fd.sort_order,
            sr.id DESC
    """

    with get_connection() as connection:
        rows = connection.execute(
            sql,
            parameters,
        ).fetchall()

    result = []

    for row in rows:
        single_stake = row["single_stake_text"] or ""

        start_stake = row["start_stake_text"] or ""

        end_stake = row["end_stake_text"] or ""

        # =========================
        # 统一工程位置
        # =========================

        if start_stake and end_stake:
            engineering_position = f"{start_stake} ～ " f"{end_stake}"

        elif start_stake:
            engineering_position = start_stake

        elif end_stake:
            engineering_position = end_stake

        else:
            engineering_position = single_stake

        form_display_name = f"附表{row['form_number']} " f"{row['form_name']}"

        result.append(
            {
                "survey_record_id": (row["survey_record_id"]),
                "engineering_asset_id": (row["engineering_asset_id"]),
                "project_id": (row["project_id"]),
                "survey_batch_id": (row["survey_batch_id"]),
                "batch_name": (row["batch_name"] or ""),
                "batch_code": (row["batch_code"] or ""),
                "form_code": (row["form_code"]),
                "form_number": (row["form_number"]),
                "form_name": (row["form_name"]),
                "form_display_name": (form_display_name),
                "asset_type": (row["asset_type"]),
                "business_code": (row["business_code"] or ""),
                "asset_name": (row["asset_name"] or ""),
                "department_name": (row["department_name"] or ""),
                "office_name": (row["office_name"] or ""),
                "canal_name": (row["canal_name"] or ""),
                "engineering_position": (engineering_position),
                "overall_grade": (row["overall_grade"]),
                "survey_date": (row["survey_date"] or ""),
                "record_status": (row["record_status"]),
                "updated_at": (row["updated_at"] or ""),
            }
        )

    return result


def _replace_inspection_results(
    connection,
    survey_record_id,
    inspection_results,
):
    """
    用当前页面提交的分项评价，
    完整替换某条调查记录已有的评价结果。

    当前只保存已经选择 A/B/C/D 的项目。
    未评价项目不写入 inspection_results。
    """

    connection.execute(
        """
        DELETE FROM inspection_results
        WHERE survey_record_id = ?
        """,
        (survey_record_id,),
    )

    for result in inspection_results:
        grade = result.get("grade")

        if grade not in ("A", "B", "C", "D"):
            continue

        connection.execute(
            """
            INSERT INTO inspection_results (
                survey_record_id,
                item_code,
                category,
                item_name,
                grade,
                description,
                remark
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                survey_record_id,
                result["item_code"],
                result["category"],
                result["item_name"],
                grade,
                result.get("description"),
                result.get("remark"),
            ),
        )


def _find_duplicate_engineering_survey(
    connection,
    project_id,
    survey_batch_id,
    form_version_id,
    organization_unit_id,
    canal_unit_id,
    single_stake_value,
    exclude_survey_record_id=None,
):
    """
    查找当前调查批次中是否已经存在同一工程调查。

    当前工程身份判定：
    - 同一项目
    - 同一调查批次
    - 同一表单定义
    - 同一水管所
    - 同一渠系
    - 同一标准化桩号

    工程名称不参与重复判定。
    """

    # 草稿允许暂时不填写桩号。
    # 没有桩号时无法可靠判断是否为同一工程，
    # 因此暂不做重复检查。
    if single_stake_value is None:
        return None

    return connection.execute(
        """
        SELECT
            sr.id AS survey_record_id,
            sr.business_code,
            sr.record_status,

            ea.id AS engineering_asset_id,
            ea.asset_name,
            ea.single_stake_text,
            ea.single_stake_value

        FROM survey_records AS sr

        JOIN engineering_assets AS ea
            ON sr.engineering_asset_id = ea.id

        JOIN form_versions AS sr_fv
            ON sr.form_version_id = sr_fv.id

        JOIN form_versions AS target_fv
            ON target_fv.id = ?

        WHERE sr.project_id = ?
        AND sr.survey_batch_id = ?

        AND sr_fv.form_definition_id
            = target_fv.form_definition_id

        AND sr.organization_unit_id = ?
        AND sr.canal_unit_id = ?

        AND ea.single_stake_value IS NOT NULL

        AND ABS(
            ea.single_stake_value - ?
        ) < 0.001

        AND (
            ? IS NULL
            OR sr.id != ?
        )

        AND sr.record_status != 'void'

        ORDER BY sr.id DESC
        LIMIT 1
        """,
        (
            form_version_id,
            project_id,
            survey_batch_id,
            organization_unit_id,
            canal_unit_id,
            single_stake_value,
            exclude_survey_record_id,
            exclude_survey_record_id,
        ),
    ).fetchone()


def create_engineering_survey(
    project_id,
    survey_batch_id,
    form_version_id,
    asset_name,
    asset_type,
    organization_unit_id,
    canal_unit_id,
    business_code,
    record_data,
    single_stake_text=None,
    single_stake_value=None,
    inspection_results=None,
    survey_date=None,
    overall_grade=None,
    survey_comment=None,
):
    """
    第一次调查时，同时创建：

    1. EngineeringAsset 工程对象
    2. SurveyRecord 本批次调查记录

    两步处于同一个 SQLite 事务中。
    任意一步失败时，全部回滚。
    """

    if not asset_name or not asset_name.strip():
        raise ValueError("工程名称不能为空。")

    if not business_code:
        raise ValueError("业务编号不能为空。")

    record_json = json.dumps(
        record_data,
        ensure_ascii=False,
    )

    with get_connection() as connection:

        duplicate = _find_duplicate_engineering_survey(
            connection=connection,
            project_id=project_id,
            survey_batch_id=survey_batch_id,
            form_version_id=form_version_id,
            organization_unit_id=organization_unit_id,
            canal_unit_id=canal_unit_id,
            single_stake_value=single_stake_value,
        )

        if duplicate is not None:
            status_text = {
                "draft": "草稿",
                "completed": "录入完成",
            }.get(
                duplicate["record_status"],
                duplicate["record_status"],
            )

            raise ValueError(
                "当前调查批次中已存在同一位置的"
                "工程调查记录。\n\n"
                f"工程名称：{duplicate['asset_name']}\n"
                f"业务编号：{duplicate['business_code']}\n"
                f"桩号：{duplicate['single_stake_text']}\n"
                f"状态：{status_text}\n\n"
                "请返回调查列表打开已有记录，"
                "不要重复新增。"
            )

        asset_cursor = connection.execute(
            """
            INSERT INTO engineering_assets (
                project_id,
                asset_name,
                asset_type,
                organization_unit_id,
                canal_unit_id,
                business_code,
                code_scheme_version,
                single_stake_text,
                single_stake_value,
                first_survey_batch_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                asset_name.strip(),
                asset_type,
                organization_unit_id,
                canal_unit_id,
                business_code,
                "V1",
                single_stake_text,
                single_stake_value,
                survey_batch_id,
            ),
        )

        engineering_asset_id = asset_cursor.lastrowid

        record_cursor = connection.execute(
            """
            INSERT INTO survey_records (
                project_id,
                survey_batch_id,
                form_version_id,
                record_type,
                organization_unit_id,
                canal_unit_id,
                engineering_asset_id,
                business_code,
                survey_date,
                overall_grade,
                survey_comment,
                record_status,
                record_data_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                survey_batch_id,
                form_version_id,
                "engineering",
                organization_unit_id,
                canal_unit_id,
                engineering_asset_id,
                business_code,
                survey_date,
                overall_grade,
                survey_comment,
                "draft",
                record_json,
            ),
        )

        survey_record_id = record_cursor.lastrowid

        if inspection_results is not None:
            _replace_inspection_results(
                connection,
                survey_record_id,
                inspection_results,
            )

        return {
            "engineering_asset_id": (engineering_asset_id),
            "survey_record_id": (survey_record_id),
            "business_code": business_code,
        }


def _find_duplicate_range_engineering_survey(
    connection,
    project_id,
    survey_batch_id,
    form_version_id,
    organization_unit_id,
    canal_unit_id,
    start_stake_value,
    end_stake_value,
    exclude_survey_record_id=None,
):
    """
    查找当前调查批次中是否已经存在
    完全相同起止桩号的区间工程调查。

    当前重复身份：
    - 同一项目；
    - 同一调查批次；
    - 同一调查表定义；
    - 同一水管所；
    - 同一渠系；
    - 同一起始桩号；
    - 同一终止桩号。

    当前不判断区间交叉或重叠。
    """

    if start_stake_value is None or end_stake_value is None:
        return None

    return connection.execute(
        """
        SELECT
            sr.id AS survey_record_id,
            sr.business_code,
            sr.record_status,

            ea.id AS engineering_asset_id,
            ea.asset_name,
            ea.start_stake_text,
            ea.start_stake_value,
            ea.end_stake_text,
            ea.end_stake_value

        FROM survey_records AS sr

        JOIN engineering_assets AS ea
            ON sr.engineering_asset_id = ea.id

        JOIN form_versions AS sr_fv
            ON sr.form_version_id = sr_fv.id

        JOIN form_versions AS target_fv
            ON target_fv.id = ?

        WHERE sr.project_id = ?
          AND sr.survey_batch_id = ?

          AND sr_fv.form_definition_id
              = target_fv.form_definition_id

          AND sr.organization_unit_id = ?
          AND sr.canal_unit_id = ?

          AND ea.start_stake_value
              IS NOT NULL

          AND ea.end_stake_value
              IS NOT NULL

          AND ABS(
              ea.start_stake_value - ?
          ) < 0.001

          AND ABS(
              ea.end_stake_value - ?
          ) < 0.001

          AND (
              ? IS NULL
              OR sr.id != ?
          )

          AND sr.record_status != 'void'

        ORDER BY sr.id DESC
        LIMIT 1
        """,
        (
            form_version_id,
            project_id,
            survey_batch_id,
            organization_unit_id,
            canal_unit_id,
            start_stake_value,
            end_stake_value,
            exclude_survey_record_id,
            exclude_survey_record_id,
        ),
    ).fetchone()


def create_range_engineering_survey(
    project_id,
    survey_batch_id,
    form_version_id,
    asset_name,
    asset_type,
    organization_unit_id,
    canal_unit_id,
    business_code,
    record_data,
    start_stake_text=None,
    start_stake_value=None,
    end_stake_text=None,
    end_stake_value=None,
    inspection_results=None,
    survey_date=None,
    overall_grade=None,
    survey_comment=None,
):
    """
    第一次保存区间型工程调查时，
    同时创建：

    1. EngineeringAsset；
    2. SurveyRecord。

    当前供附表2.5、2.7等
    起止桩号工程共同使用。
    """

    if not asset_name or not asset_name.strip():
        raise ValueError("工程名称不能为空。")

    if not business_code:
        raise ValueError("业务编号不能为空。")

    record_json = json.dumps(
        record_data,
        ensure_ascii=False,
    )

    with get_connection() as connection:
        duplicate = _find_duplicate_range_engineering_survey(
            connection=connection,
            project_id=project_id,
            survey_batch_id=survey_batch_id,
            form_version_id=form_version_id,
            organization_unit_id=(organization_unit_id),
            canal_unit_id=canal_unit_id,
            start_stake_value=(start_stake_value),
            end_stake_value=(end_stake_value),
        )

        if duplicate is not None:
            status_text = {
                "draft": "草稿",
                "completed": "录入完成",
            }.get(
                duplicate["record_status"],
                duplicate["record_status"],
            )

            raise ValueError(
                "当前调查批次中已存在"
                "相同起止桩号的工程调查记录。"
                "\n\n"
                f"工程名称："
                f"{duplicate['asset_name']}\n"
                f"业务编号："
                f"{duplicate['business_code']}\n"
                f"工程位置："
                f"{duplicate['start_stake_text']}"
                " ～ "
                f"{duplicate['end_stake_text']}\n"
                f"状态：{status_text}\n\n"
                "请返回调查列表打开已有记录，"
                "不要重复新增。"
            )

        asset_cursor = connection.execute(
            """
            INSERT INTO engineering_assets (
                project_id,
                asset_name,
                asset_type,
                organization_unit_id,
                canal_unit_id,
                business_code,
                code_scheme_version,

                single_stake_text,
                single_stake_value,

                start_stake_text,
                start_stake_value,
                end_stake_text,
                end_stake_value,

                first_survey_batch_id
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                NULL, NULL,
                ?, ?, ?, ?,
                ?
            )
            """,
            (
                project_id,
                asset_name.strip(),
                asset_type,
                organization_unit_id,
                canal_unit_id,
                business_code,
                "V1",
                start_stake_text,
                start_stake_value,
                end_stake_text,
                end_stake_value,
                survey_batch_id,
            ),
        )

        engineering_asset_id = asset_cursor.lastrowid

        record_cursor = connection.execute(
            """
            INSERT INTO survey_records (
                project_id,
                survey_batch_id,
                form_version_id,
                record_type,
                organization_unit_id,
                canal_unit_id,
                engineering_asset_id,
                business_code,
                survey_date,
                overall_grade,
                survey_comment,
                record_status,
                record_data_json
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            )
            """,
            (
                project_id,
                survey_batch_id,
                form_version_id,
                "engineering",
                organization_unit_id,
                canal_unit_id,
                engineering_asset_id,
                business_code,
                survey_date,
                overall_grade,
                survey_comment,
                "draft",
                record_json,
            ),
        )

        survey_record_id = record_cursor.lastrowid

        if inspection_results is not None:
            _replace_inspection_results(
                connection,
                survey_record_id,
                inspection_results,
            )

        return {
            "engineering_asset_id": (engineering_asset_id),
            "survey_record_id": (survey_record_id),
            "business_code": business_code,
        }


def _find_duplicate_lined_channel_section_survey(
    connection,
    project_id,
    survey_batch_id,
    form_version_id,
    organization_unit_id,
    canal_unit_id,
    start_stake_value,
    end_stake_value,
    exclude_survey_record_id=None,
):
    """
    查找当前调查批次中是否已经存在
    完全相同起止桩号的附表2.1渠段调查。

    当前重复身份：
    - 同一项目
    - 同一调查批次
    - 同一表单定义
    - 同一水管所
    - 同一渠系
    - 同一起始桩号
    - 同一终止桩号

    当前不判断渠段交叉或重叠。
    """

    # 草稿允许暂时没有完整起止桩号。
    # 任一端缺失时暂时无法可靠判断重复。
    if start_stake_value is None or end_stake_value is None:
        return None

    return connection.execute(
        """
        SELECT
            sr.id AS survey_record_id,
            sr.business_code,
            sr.record_status,

            ea.id AS engineering_asset_id,
            ea.asset_name,
            ea.start_stake_text,
            ea.start_stake_value,
            ea.end_stake_text,
            ea.end_stake_value

        FROM survey_records AS sr

        JOIN engineering_assets AS ea
            ON sr.engineering_asset_id = ea.id

        JOIN form_versions AS sr_fv
            ON sr.form_version_id = sr_fv.id

        JOIN form_versions AS target_fv
            ON target_fv.id = ?

        WHERE sr.project_id = ?
          AND sr.survey_batch_id = ?

          AND sr_fv.form_definition_id
              = target_fv.form_definition_id

          AND sr.organization_unit_id = ?
          AND sr.canal_unit_id = ?

          AND ea.start_stake_value IS NOT NULL
          AND ea.end_stake_value IS NOT NULL

          AND ABS(
              ea.start_stake_value - ?
          ) < 0.001

          AND ABS(
              ea.end_stake_value - ?
          ) < 0.001

          AND (
              ? IS NULL
              OR sr.id != ?
          )

          AND sr.record_status != 'void'

        ORDER BY sr.id DESC
        LIMIT 1
        """,
        (
            form_version_id,
            project_id,
            survey_batch_id,
            organization_unit_id,
            canal_unit_id,
            start_stake_value,
            end_stake_value,
            exclude_survey_record_id,
            exclude_survey_record_id,
        ),
    ).fetchone()


def create_lined_channel_section_survey(
    project_id,
    survey_batch_id,
    form_version_id,
    asset_name,
    organization_unit_id,
    canal_unit_id,
    business_code,
    record_data,
    start_stake_text=None,
    start_stake_value=None,
    end_stake_text=None,
    end_stake_value=None,
    inspection_results=None,
    survey_date=None,
    overall_grade=None,
    survey_comment=None,
):
    """
    第一次创建附表2.1防渗衬砌渠道渠段调查时，
    同时创建：

    1. EngineeringAsset 渠段工程对象
    2. SurveyRecord 本批次调查记录

    当前 V0.3.0-A1 仅验证渠段型工程的数据模型，
    暂不处理：
    - 重复渠段检查
    - 分项评价
    - 完成调查
    - 2.1完整字段校验

    与附表2.2不同：
    - single_stake_* 保持为空；
    - 使用 start_stake_* 和 end_stake_*。
    """

    if not asset_name or not asset_name.strip():
        raise ValueError("渠道名称不能为空。")

    if not business_code:
        raise ValueError("业务编号不能为空。")

    record_json = json.dumps(
        record_data,
        ensure_ascii=False,
    )

    with get_connection() as connection:
        duplicate = _find_duplicate_lined_channel_section_survey(
            connection=connection,
            project_id=project_id,
            survey_batch_id=survey_batch_id,
            form_version_id=form_version_id,
            organization_unit_id=(organization_unit_id),
            canal_unit_id=canal_unit_id,
            start_stake_value=(start_stake_value),
            end_stake_value=(end_stake_value),
        )

        if duplicate is not None:
            status_text = {
                "draft": "草稿",
                "completed": "录入完成",
            }.get(
                duplicate["record_status"],
                duplicate["record_status"],
            )

            raise ValueError(
                "当前调查批次中已存在相同起止桩号的"
                "渠道渠段调查记录。\n\n"
                f"渠道名称："
                f"{duplicate['asset_name']}\n"
                f"业务编号："
                f"{duplicate['business_code']}\n"
                f"渠段："
                f"{duplicate['start_stake_text']}"
                " ～ "
                f"{duplicate['end_stake_text']}\n"
                f"状态：{status_text}\n\n"
                "请返回调查列表打开已有记录，"
                "不要重复新增。"
            )

        asset_cursor = connection.execute(
            """
            INSERT INTO engineering_assets (
                project_id,
                asset_name,
                asset_type,
                organization_unit_id,
                canal_unit_id,
                business_code,
                code_scheme_version,
                start_stake_text,
                start_stake_value,
                end_stake_text,
                end_stake_value,
                first_survey_batch_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                asset_name.strip(),
                "lined_channel_section",
                organization_unit_id,
                canal_unit_id,
                business_code,
                "V1",
                start_stake_text,
                start_stake_value,
                end_stake_text,
                end_stake_value,
                survey_batch_id,
            ),
        )

        engineering_asset_id = asset_cursor.lastrowid

        record_cursor = connection.execute(
            """
            INSERT INTO survey_records (
                project_id,
                survey_batch_id,
                form_version_id,
                record_type,
                organization_unit_id,
                canal_unit_id,
                engineering_asset_id,
                business_code,
                survey_date,
                overall_grade,
                survey_comment,
                record_status,
                record_data_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                survey_batch_id,
                form_version_id,
                "engineering",
                organization_unit_id,
                canal_unit_id,
                engineering_asset_id,
                business_code,
                survey_date,
                overall_grade,
                survey_comment,
                "draft",
                record_json,
            ),
        )

        survey_record_id = record_cursor.lastrowid

        if inspection_results is not None:
            _replace_inspection_results(
                connection,
                survey_record_id,
                inspection_results,
            )

        return {
            "engineering_asset_id": engineering_asset_id,
            "survey_record_id": survey_record_id,
            "business_code": business_code,
        }


def get_lined_channel_section_records(
    project_id,
    survey_batch_id,
):
    """
    获取当前项目、当前调查批次下的
    附表2.1防渗衬砌渠道渠段调查记录。

    当前供后续2.1调查列表页面使用。
    """

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                sr.id AS survey_record_id,
                sr.business_code,
                sr.record_status,
                sr.overall_grade,                
                sr.record_data_json,
                sr.updated_at,

                ea.id AS engineering_asset_id,
                ea.asset_name,
                ea.start_stake_text,
                ea.start_stake_value,
                ea.end_stake_text,
                ea.end_stake_value,

                office.name AS office_name,
                department.name AS department_name,

                canal.name AS canal_name

            FROM survey_records AS sr

            JOIN engineering_assets AS ea
                ON sr.engineering_asset_id = ea.id

            JOIN form_versions AS fv
                ON sr.form_version_id = fv.id

            JOIN form_definitions AS fd
                ON fv.form_definition_id = fd.id

            LEFT JOIN organization_units AS office
                ON sr.organization_unit_id = office.id

            LEFT JOIN organization_units AS department
                ON office.parent_id = department.id

            LEFT JOIN canal_units AS canal
                ON sr.canal_unit_id = canal.id

            WHERE sr.project_id = ?
              AND sr.survey_batch_id = ?
              AND fd.form_code = 'form_2_1'
              AND sr.record_status != 'void'

            ORDER BY sr.id DESC
            """,
            (
                project_id,
                survey_batch_id,
            ),
        ).fetchall()

        result = []

        for row in rows:
            try:
                record_data = json.loads(row["record_data_json"] or "{}")
            except json.JSONDecodeError:
                record_data = {}

            result.append(
                {
                    "survey_record_id": (row["survey_record_id"]),
                    "engineering_asset_id": (row["engineering_asset_id"]),
                    "business_code": (row["business_code"] or ""),
                    "asset_name": (row["asset_name"] or ""),
                    "department_name": (row["department_name"] or ""),
                    "office_name": (row["office_name"] or ""),
                    "canal_name": (row["canal_name"] or ""),
                    "start_stake_text": (row["start_stake_text"] or ""),
                    "end_stake_text": (row["end_stake_text"] or ""),
                    "record_status": (row["record_status"]),
                    "updated_at": (row["updated_at"]),
                    "record_data": record_data,
                    "overall_grade": (row["overall_grade"]),
                }
            )

        return result


def get_lined_channel_section_record(
    survey_record_id,
):
    """
    获取一条附表2.1渠段调查记录，
    用于草稿重新打开和页面回填。
    """

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                sr.id AS survey_record_id,
                sr.project_id,
                sr.survey_batch_id,
                sr.form_version_id,
                sr.organization_unit_id,
                sr.canal_unit_id,
                sr.business_code,
                sr.record_status,
                sr.record_data_json,
                sr.survey_date,
                sr.overall_grade,
                sr.survey_comment,

                ea.id AS engineering_asset_id,
                ea.asset_name,
                ea.asset_type,
                department.id AS department_id,
                ea.single_stake_text,
                ea.single_stake_value,
                ea.start_stake_text,
                ea.start_stake_value,
                ea.end_stake_text,
                ea.end_stake_value,

                fd.form_code

            FROM survey_records AS sr

            JOIN engineering_assets AS ea
                ON sr.engineering_asset_id = ea.id

            JOIN form_versions AS fv
                ON sr.form_version_id = fv.id

            JOIN form_definitions AS fd
                ON fv.form_definition_id = fd.id

            LEFT JOIN organization_units AS office
                ON sr.organization_unit_id = office.id

            LEFT JOIN organization_units AS department
                ON office.parent_id = department.id

            WHERE sr.id = ?
            LIMIT 1
            """,
            (survey_record_id,),
        ).fetchone()

        if row is None:
            raise ValueError("没有找到指定的渠道渠段调查记录。")

        if row["form_code"] != "form_2_1":
            raise ValueError("指定记录不是附表2.1调查记录。")

        try:
            record_data = json.loads(row["record_data_json"] or "{}")
        except json.JSONDecodeError:
            record_data = {}

        return {
            "survey_record_id": (row["survey_record_id"]),
            "engineering_asset_id": (row["engineering_asset_id"]),
            "project_id": (row["project_id"]),
            "survey_batch_id": (row["survey_batch_id"]),
            "form_version_id": (row["form_version_id"]),
            "organization_unit_id": (row["organization_unit_id"]),
            "canal_unit_id": (row["canal_unit_id"]),
            "business_code": (row["business_code"] or ""),
            "record_status": (row["record_status"]),
            "asset_name": (row["asset_name"] or ""),
            "asset_type": (row["asset_type"]),
            "start_stake_text": (row["start_stake_text"] or ""),
            "start_stake_value": (row["start_stake_value"]),
            "end_stake_text": (row["end_stake_text"] or ""),
            "end_stake_value": (row["end_stake_value"]),
            "record_data": record_data,
            "single_stake_text": (row["single_stake_text"]),
            "single_stake_value": (row["single_stake_value"]),
            "department_id": (row["department_id"]),
            "survey_date": (row["survey_date"]),
            "overall_grade": (row["overall_grade"]),
            "survey_comment": (row["survey_comment"] or ""),
        }


def update_lined_channel_section_draft(
    survey_record_id,
    asset_name,
    organization_unit_id,
    canal_unit_id,
    business_code,
    record_data,
    start_stake_text=None,
    start_stake_value=None,
    end_stake_text=None,
    end_stake_value=None,
    inspection_results=None,
    survey_date=None,
    overall_grade=None,
    survey_comment=None,
):
    """
    修改附表2.1渠段调查草稿。

    当前阶段只允许修改 draft 记录。
    EngineeringAsset 与 SurveyRecord
    在同一个事务中同步更新。
    """

    if not asset_name or not asset_name.strip():
        raise ValueError("渠道名称不能为空。")

    if not business_code:
        raise ValueError("业务编号不能为空。")

    record_json = json.dumps(
        record_data,
        ensure_ascii=False,
    )

    with get_connection() as connection:
        existing = connection.execute(
            """
            SELECT
                sr.id AS survey_record_id,
                sr.engineering_asset_id,
                sr.record_status,
                sr.project_id,
                sr.survey_batch_id,
                sr.form_version_id,
                sr.organization_unit_id,
                sr.canal_unit_id,

                fd.form_code

            FROM survey_records AS sr

            JOIN form_versions AS fv
                ON sr.form_version_id = fv.id

            JOIN form_definitions AS fd
                ON fv.form_definition_id = fd.id

            WHERE sr.id = ?
            LIMIT 1
            """,
            (survey_record_id,),
        ).fetchone()

        if existing is None:
            raise ValueError("没有找到指定的渠道渠段调查记录。")

        if existing["form_code"] != "form_2_1":
            raise ValueError("指定记录不是附表2.1调查记录。")

        if existing["record_status"] not in (
            "draft",
            "completed",
        ):
            raise ValueError("当前调查记录状态不支持修改。")

        duplicate = _find_duplicate_lined_channel_section_survey(
            connection=connection,
            project_id=existing["project_id"],
            survey_batch_id=existing["survey_batch_id"],
            form_version_id=existing["form_version_id"],
            organization_unit_id=(organization_unit_id),
            canal_unit_id=canal_unit_id,
            start_stake_value=(start_stake_value),
            end_stake_value=(end_stake_value),
            exclude_survey_record_id=(survey_record_id),
        )

        if duplicate is not None:
            status_text = {
                "draft": "草稿",
                "completed": "录入完成",
            }.get(
                duplicate["record_status"],
                duplicate["record_status"],
            )

            raise ValueError(
                "当前调查批次中已存在相同起止桩号的"
                "渠道渠段调查记录。\n\n"
                f"渠道名称："
                f"{duplicate['asset_name']}\n"
                f"业务编号："
                f"{duplicate['business_code']}\n"
                f"渠段："
                f"{duplicate['start_stake_text']}"
                " ～ "
                f"{duplicate['end_stake_text']}\n"
                f"状态：{status_text}\n\n"
                "当前记录不能修改为该渠段。"
            )

        engineering_asset_id = existing["engineering_asset_id"]

        connection.execute(
            """
            UPDATE engineering_assets
            SET
                asset_name = ?,
                organization_unit_id = ?,
                canal_unit_id = ?,
                business_code = ?,
                single_stake_text = NULL,
                single_stake_value = NULL,
                start_stake_text = ?,
                start_stake_value = ?,
                end_stake_text = ?,
                end_stake_value = ?,
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (
                asset_name.strip(),
                organization_unit_id,
                canal_unit_id,
                business_code,
                start_stake_text,
                start_stake_value,
                end_stake_text,
                end_stake_value,
                engineering_asset_id,
            ),
        )

        connection.execute(
            """
            UPDATE survey_records
            SET
                organization_unit_id = ?,
                canal_unit_id = ?,
                business_code = ?,
                survey_date = ?,
                overall_grade = ?,
                survey_comment = ?,
                record_data_json = ?,
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (
                organization_unit_id,
                canal_unit_id,
                business_code,
                survey_date,
                overall_grade,
                survey_comment,
                record_json,
                survey_record_id,
            ),
        )

        if inspection_results is not None:
            _replace_inspection_results(
                connection,
                survey_record_id,
                inspection_results,
            )

        return {
            "engineering_asset_id": (engineering_asset_id),
            "survey_record_id": (survey_record_id),
            "business_code": business_code,
        }


def complete_lined_channel_section_record(
    survey_record_id,
):
    """
    将附表2.1渠道渠段调查草稿标记为 completed。

    完成要求：
    - 工程及归属信息完整；
    - 附表2.1基本信息完整；
    - 加固改造年月允许为空；
    - 12项分项评价全部完成；
    - 工程状况类别已确定；
    - 调查时间有效；
    - 调查意见与建议已填写。
    """

    with get_connection() as connection:
        record = connection.execute(
            """
            SELECT
                sr.id,
                sr.record_status,
                sr.organization_unit_id,
                sr.canal_unit_id,
                sr.business_code,
                sr.survey_date,
                sr.overall_grade,
                sr.survey_comment,
                sr.record_data_json,

                ea.asset_name,
                ea.start_stake_text,
                ea.start_stake_value,
                ea.end_stake_text,
                ea.end_stake_value,

                fd.form_code

            FROM survey_records AS sr

            JOIN engineering_assets AS ea
                ON sr.engineering_asset_id = ea.id

            JOIN form_versions AS fv
                ON sr.form_version_id = fv.id

            JOIN form_definitions AS fd
                ON fv.form_definition_id = fd.id

            WHERE sr.id = ?
            """,
            (survey_record_id,),
        ).fetchone()

        if record is None:
            raise ValueError("没有找到该调查记录。")

        if record["form_code"] != "form_2_1":
            raise ValueError("指定记录不是附表2.1调查记录。")

        if record["record_status"] != "draft":
            raise ValueError("只有草稿记录可以执行完成调查。")

        try:
            record_data = json.loads(record["record_data_json"] or "{}")
        except json.JSONDecodeError:
            raise ValueError("当前调查记录数据异常，" "无法执行完成调查。")

        missing_fields = []

        def is_missing(value):
            if value is None:
                return True

            if isinstance(value, str):
                return not value.strip()

            return False

        # =========================
        # 工程身份
        # =========================

        if is_missing(record["asset_name"]):
            missing_fields.append("渠道名称")

        if record["organization_unit_id"] is None:
            missing_fields.append("所属水管所")

        if record["canal_unit_id"] is None:
            missing_fields.append("所属渠系")

        if is_missing(record["business_code"]):
            missing_fields.append("业务编号")

        if is_missing(record["start_stake_text"]):
            missing_fields.append("起始桩号")

        if is_missing(record["end_stake_text"]):
            missing_fields.append("终止桩号")

        # =========================
        # 基本信息
        # =========================

        required_record_fields = {
            "section_length": "渠段长度",
            "build_date": "建成年月",
            "longitudinal_slope": "纵比降",
            "design_flow": "设计流量",
            "channel_grade": "渠道等级",
            "cross_section_form": "渠道断面形式",
            "embankment_top_width": "堤顶宽度",
            "inner_slope": "渠道边坡（内）",
            "outer_slope": "渠道边坡（外）",
            "increased_flow": "加大流量",
            "bed_soil": "渠床土质",
            "lining_structure": "防渗衬砌结构",
            "freeboard": "安全超高",
            "bottom_width": "渠底宽度",
            "water_conveyance_loss": "输水损失",
            "lining_material": "衬砌材料",
            "lining_thickness": "衬砌厚度",
            "concrete_strength": "混凝土强度",
            "channel_depth": "渠深",
            "channel_bottom_elevation": "渠底高程",
        }

        for field_key, field_name in required_record_fields.items():
            if is_missing(record_data.get(field_key)):
                missing_fields.append(field_name)

        if is_missing(record["survey_date"]):
            missing_fields.append("调查时间")

        if record["overall_grade"] not in (
            "A",
            "B",
            "C",
            "D",
        ):
            missing_fields.append("工程状况类别")

        if is_missing(record["survey_comment"]):
            missing_fields.append("调查意见与建议")

        if missing_fields:
            field_text = "、".join(missing_fields)

            raise ValueError("完成调查前仍有必填内容未填写：" f"{field_text}。")

        # =========================
        # 桩号逻辑
        # =========================

        if (
            record["start_stake_value"] is not None
            and record["end_stake_value"] is not None
            and record["end_stake_value"] < record["start_stake_value"]
        ):
            raise ValueError("终止桩号不能小于起始桩号。")

        # =========================
        # 日期
        # =========================

        try:
            datetime.strptime(
                record_data["build_date"],
                "%Y-%m",
            )
        except (TypeError, ValueError):
            raise ValueError("建成年月不是有效的 YYYY-MM 日期。")

        renovation_date = record_data.get("renovation_date")

        if renovation_date:
            try:
                datetime.strptime(
                    renovation_date,
                    "%Y-%m",
                )
            except (TypeError, ValueError):
                raise ValueError("加固改造年月不是有效的 " "YYYY-MM 日期。")

        try:
            datetime.strptime(
                record["survey_date"],
                "%Y-%m-%d",
            )
        except (TypeError, ValueError):
            raise ValueError("调查时间不是有效的 " "YYYY-MM-DD 日期。")

        # =========================
        # 12项评价
        # =========================

        inspection_count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM inspection_results
            WHERE survey_record_id = ?
            """,
            (survey_record_id,),
        ).fetchone()["count"]

        if inspection_count != 12:
            raise ValueError(
                "完成调查前必须完成全部12项"
                "分项评价。"
                f"当前已完成 {inspection_count} 项。"
            )

        connection.execute(
            """
            UPDATE survey_records
            SET
                record_status = 'completed',
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (survey_record_id,),
        )

        return {
            "survey_record_id": (survey_record_id),
            "inspection_count": (inspection_count),
        }


def get_sluice_gate_records(
    project_id,
    survey_batch_id,
):
    """
    获取当前项目、当前调查批次下的附表2.2水闸调查记录。
    """

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                sr.id AS survey_record_id,
                sr.business_code,
                sr.record_status,
                sr.overall_grade,
                sr.record_data_json,
                sr.updated_at,

                ea.id AS engineering_asset_id,
                ea.asset_name,

                office.name AS office_name,
                department.name AS department_name,

                canal.name AS canal_name

            FROM survey_records AS sr

            JOIN engineering_assets AS ea
                ON sr.engineering_asset_id = ea.id

            JOIN form_versions AS fv
                ON sr.form_version_id = fv.id

            JOIN form_definitions AS fd
                ON fv.form_definition_id = fd.id

            LEFT JOIN organization_units AS office
                ON sr.organization_unit_id = office.id

            LEFT JOIN organization_units AS department
                ON office.parent_id = department.id

            LEFT JOIN canal_units AS canal
                ON sr.canal_unit_id = canal.id

            WHERE sr.project_id = ?
              AND sr.survey_batch_id = ?
              AND fd.form_code = 'form_2_2'
              AND sr.record_status != 'void'

            ORDER BY sr.id DESC
            """,
            (
                project_id,
                survey_batch_id,
            ),
        ).fetchall()

        result = []

        for row in rows:
            try:
                record_data = json.loads(row["record_data_json"] or "{}")
            except json.JSONDecodeError:
                record_data = {}

            result.append(
                {
                    "survey_record_id": (row["survey_record_id"]),
                    "engineering_asset_id": (row["engineering_asset_id"]),
                    "business_code": (row["business_code"] or ""),
                    "asset_name": (row["asset_name"] or ""),
                    "department_name": (row["department_name"] or ""),
                    "office_name": (row["office_name"] or ""),
                    "canal_name": (row["canal_name"] or ""),
                    "stake": (record_data.get("stake") or ""),
                    "design_flow": (record_data.get("design_flow")),
                    "overall_grade": (row["overall_grade"]),
                    "record_status": (row["record_status"]),
                    "updated_at": (row["updated_at"]),
                }
            )

        return result


def delete_engineering_survey_record(
    survey_record_id,
    form_code,
):
    """
    删除一条工程调查记录。

    当前供附表2系列工程调查表共同使用。

    删除规则：
    1. survey_record_id 必须属于指定 form_code；
    2. 删除 SurveyRecord；
    3. InspectionResult 由外键级联删除；
    4. 如果对应 EngineeringAsset
       已经没有其他调查记录，
       同时删除该工程对象；
    5. 全部操作处于同一个 SQLite 事务中。
    """

    with get_connection() as connection:
        record = connection.execute(
            """
            SELECT
                sr.id AS survey_record_id,
                sr.engineering_asset_id,
                sr.business_code,
                sr.record_status,

                ea.asset_name,
                ea.single_stake_text,
                ea.start_stake_text,
                ea.end_stake_text,

                fd.form_code

            FROM survey_records AS sr

            JOIN engineering_assets AS ea
                ON sr.engineering_asset_id = ea.id

            JOIN form_versions AS fv
                ON sr.form_version_id = fv.id

            JOIN form_definitions AS fd
                ON fv.form_definition_id = fd.id

            WHERE sr.id = ?
              AND fd.form_code = ?
            """,
            (
                survey_record_id,
                form_code,
            ),
        ).fetchone()

        if record is None:
            raise ValueError("没有找到指定调查记录，" "或该记录不属于当前调查表。")

        engineering_asset_id = record["engineering_asset_id"]

        # =========================
        # 1. 删除调查记录
        # =========================
        #
        # inspection_results 已配置：
        # ON DELETE CASCADE
        # 因此相关评价结果自动一起删除。
        # =========================

        connection.execute(
            """
            DELETE FROM survey_records
            WHERE id = ?
            """,
            (survey_record_id,),
        )

        # =========================
        # 2. 检查工程对象是否仍被引用
        # =========================

        remaining_count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM survey_records
            WHERE engineering_asset_id = ?
            """,
            (engineering_asset_id,),
        ).fetchone()["count"]

        asset_deleted = False

        # =========================
        # 3. 清理孤立 EngineeringAsset
        # =========================

        if remaining_count == 0:
            connection.execute(
                """
                DELETE FROM engineering_assets
                WHERE id = ?
                """,
                (engineering_asset_id,),
            )

            asset_deleted = True

        return {
            "survey_record_id": (survey_record_id),
            "engineering_asset_id": (engineering_asset_id),
            "business_code": (record["business_code"]),
            "asset_name": (record["asset_name"]),
            "record_status": (record["record_status"]),
            "form_code": (record["form_code"]),
            "single_stake_text": (record["single_stake_text"]),
            "start_stake_text": (record["start_stake_text"]),
            "end_stake_text": (record["end_stake_text"]),
            "asset_deleted": (asset_deleted),
            "remaining_survey_count": (remaining_count),
        }


def delete_lined_channel_section_record(
    survey_record_id,
):
    """
    删除一条附表2.1渠道渠段调查记录。

    保留原函数作为兼容入口，
    实际删除逻辑统一走工程调查公共函数。
    """

    return delete_engineering_survey_record(
        survey_record_id=(survey_record_id),
        form_code="form_2_1",
    )


def delete_sluice_gate_record(
    survey_record_id,
):
    """
    删除一条附表2.2水闸调查记录。

    保留原函数作为兼容入口，
    实际删除逻辑统一走工程调查公共函数。
    """

    return delete_engineering_survey_record(
        survey_record_id=(survey_record_id),
        form_code="form_2_2",
    )


def get_point_engineering_record(
    survey_record_id,
    form_code,
):
    """
    获取一条点状工程调查记录。

    当前供附表2.2、2.3等使用单桩号的
    工程调查表共同使用。

    form_code 用于保证：
    调查页面只能打开属于自己的调查记录。
    """

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                sr.id AS survey_record_id,
                sr.record_status,
                sr.business_code,
                sr.record_data_json,
                sr.survey_date,
                sr.overall_grade,
                sr.survey_comment,

                ea.id AS engineering_asset_id,
                ea.asset_name,
                ea.asset_type,
                ea.single_stake_text,
                ea.single_stake_value,

                office.id AS office_id,
                department.id AS department_id,

                canal.id AS canal_id,

                fd.form_code

            FROM survey_records AS sr

            JOIN engineering_assets AS ea
                ON sr.engineering_asset_id = ea.id

            JOIN form_versions AS fv
                ON sr.form_version_id = fv.id

            JOIN form_definitions AS fd
                ON fv.form_definition_id = fd.id

            LEFT JOIN organization_units AS office
                ON sr.organization_unit_id = office.id

            LEFT JOIN organization_units AS department
                ON office.parent_id = department.id

            LEFT JOIN canal_units AS canal
                ON sr.canal_unit_id = canal.id

            WHERE sr.id = ?
              AND fd.form_code = ?
            """,
            (
                survey_record_id,
                form_code,
            ),
        ).fetchone()

        if row is None:
            return None

        try:
            record_data = json.loads(row["record_data_json"] or "{}")
        except json.JSONDecodeError:
            record_data = {}

        return {
            "survey_record_id": (row["survey_record_id"]),
            "engineering_asset_id": (row["engineering_asset_id"]),
            "record_status": (row["record_status"]),
            "business_code": (row["business_code"] or ""),
            "asset_name": (row["asset_name"] or ""),
            "asset_type": (row["asset_type"]),
            "form_code": (row["form_code"]),
            "single_stake_text": (row["single_stake_text"]),
            "single_stake_value": (row["single_stake_value"]),
            "department_id": (row["department_id"]),
            "office_id": (row["office_id"]),
            "canal_id": (row["canal_id"]),
            "record_data": record_data,
            "survey_date": (row["survey_date"]),
            "overall_grade": (row["overall_grade"]),
            "survey_comment": (row["survey_comment"] or ""),
        }


def get_sluice_gate_record(
    survey_record_id,
):
    """
    获取一条附表2.2水闸调查记录。

    保留原函数作为兼容入口，
    实际读取逻辑统一走点状工程公共函数。
    """

    return get_point_engineering_record(
        survey_record_id=survey_record_id,
        form_code="form_2_2",
    )


def get_inspection_results(
    survey_record_id,
):
    """
    获取某条调查记录已经保存的分项评价结果。
    """
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT
                item_code,
                category,
                item_name,
                grade,
                description,
                remark
            FROM inspection_results
            WHERE survey_record_id = ?
            ORDER BY id
            """,
            (survey_record_id,),
        ).fetchall()


def update_point_engineering_survey(
    survey_record_id,
    form_code,
    asset_name,
    record_data,
    single_stake_text=None,
    single_stake_value=None,
    inspection_results=None,
    survey_date=None,
    overall_grade=None,
    survey_comment=None,
):
    """
    修改已有点状工程调查记录。

    当前供附表2.2、2.3等单桩号工程共同使用。

    允许修改：
    - draft 草稿；
    - completed 已完成记录。

    不允许通过此函数修改：
    - 所属机构；
    - 所属渠系；
    - 业务编号；
    - 调查表类型。
    """

    if not asset_name or not asset_name.strip():
        raise ValueError("工程名称不能为空。")

    record_json = json.dumps(
        record_data,
        ensure_ascii=False,
    )

    with get_connection() as connection:
        record = connection.execute(
            """
            SELECT
                sr.engineering_asset_id,
                sr.record_status,
                sr.project_id,
                sr.survey_batch_id,
                sr.form_version_id,
                sr.organization_unit_id,
                sr.canal_unit_id,

                fd.form_code

            FROM survey_records AS sr

            JOIN form_versions AS fv
                ON sr.form_version_id = fv.id

            JOIN form_definitions AS fd
                ON fv.form_definition_id = fd.id

            WHERE sr.id = ?
              AND fd.form_code = ?
            """,
            (
                survey_record_id,
                form_code,
            ),
        ).fetchone()

        # 必须先判断记录是否存在，
        # 再访问 record 中的字段。
        if record is None:
            raise ValueError("没有找到该调查记录。")

        if record["record_status"] not in (
            "draft",
            "completed",
        ):
            raise ValueError("当前记录状态不允许直接修改。")

        duplicate = _find_duplicate_engineering_survey(
            connection=connection,
            project_id=(record["project_id"]),
            survey_batch_id=(record["survey_batch_id"]),
            form_version_id=(record["form_version_id"]),
            organization_unit_id=(record["organization_unit_id"]),
            canal_unit_id=(record["canal_unit_id"]),
            single_stake_value=(single_stake_value),
            exclude_survey_record_id=(survey_record_id),
        )

        if duplicate is not None:
            status_text = {
                "draft": "草稿",
                "completed": "录入完成",
            }.get(
                duplicate["record_status"],
                duplicate["record_status"],
            )

            raise ValueError(
                "当前调查批次中已存在同一位置的"
                "工程调查记录。\n\n"
                f"工程名称："
                f"{duplicate['asset_name']}\n"
                f"业务编号："
                f"{duplicate['business_code']}\n"
                f"桩号："
                f"{duplicate['single_stake_text']}\n"
                f"状态：{status_text}\n\n"
                "当前记录不能修改为该桩号。"
            )

        engineering_asset_id = record["engineering_asset_id"]

        connection.execute(
            """
            UPDATE engineering_assets
            SET
                asset_name = ?,
                single_stake_text = ?,
                single_stake_value = ?,
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (
                asset_name.strip(),
                single_stake_text,
                single_stake_value,
                engineering_asset_id,
            ),
        )

        connection.execute(
            """
            UPDATE survey_records
            SET
                survey_date = ?,
                overall_grade = ?,
                survey_comment = ?,
                record_data_json = ?,
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (
                survey_date,
                overall_grade,
                survey_comment,
                record_json,
                survey_record_id,
            ),
        )

        if inspection_results is not None:
            _replace_inspection_results(
                connection,
                survey_record_id,
                inspection_results,
            )


def get_range_engineering_record(
    survey_record_id,
    form_code,
):
    """
    获取一条区间型工程调查记录。

    当前供附表2.5、2.7等
    起止桩号工程共同使用。
    """

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                sr.id
                    AS survey_record_id,

                sr.record_status,
                sr.business_code,
                sr.record_data_json,
                sr.survey_date,
                sr.overall_grade,
                sr.survey_comment,

                ea.id
                    AS engineering_asset_id,

                ea.asset_name,
                ea.asset_type,

                ea.start_stake_text,
                ea.start_stake_value,
                ea.end_stake_text,
                ea.end_stake_value,

                office.id AS office_id,
                department.id
                    AS department_id,

                canal.id AS canal_id,

                fd.form_code

            FROM survey_records AS sr

            JOIN engineering_assets AS ea
                ON sr.engineering_asset_id
                    = ea.id

            JOIN form_versions AS fv
                ON sr.form_version_id
                    = fv.id

            JOIN form_definitions AS fd
                ON fv.form_definition_id
                    = fd.id

            LEFT JOIN organization_units
                AS office
                ON sr.organization_unit_id
                    = office.id

            LEFT JOIN organization_units
                AS department
                ON office.parent_id
                    = department.id

            LEFT JOIN canal_units AS canal
                ON sr.canal_unit_id
                    = canal.id

            WHERE sr.id = ?
              AND fd.form_code = ?
              AND sr.record_status
                    != 'void'
            """,
            (
                survey_record_id,
                form_code,
            ),
        ).fetchone()

    if row is None:
        return None

    try:
        record_data = json.loads(row["record_data_json"] or "{}")
    except json.JSONDecodeError:
        record_data = {}

    return {
        "survey_record_id": (row["survey_record_id"]),
        "engineering_asset_id": (row["engineering_asset_id"]),
        "record_status": (row["record_status"]),
        "business_code": (row["business_code"] or ""),
        "asset_name": (row["asset_name"] or ""),
        "asset_type": (row["asset_type"]),
        "form_code": (row["form_code"]),
        "start_stake_text": (row["start_stake_text"]),
        "start_stake_value": (row["start_stake_value"]),
        "end_stake_text": (row["end_stake_text"]),
        "end_stake_value": (row["end_stake_value"]),
        "department_id": (row["department_id"]),
        "office_id": (row["office_id"]),
        "canal_id": (row["canal_id"]),
        "record_data": record_data,
        "survey_date": (row["survey_date"]),
        "overall_grade": (row["overall_grade"]),
        "survey_comment": (row["survey_comment"] or ""),
    }


def update_range_engineering_survey(
    survey_record_id,
    form_code,
    asset_name,
    record_data,
    start_stake_text=None,
    start_stake_value=None,
    end_stake_text=None,
    end_stake_value=None,
    inspection_results=None,
    survey_date=None,
    overall_grade=None,
    survey_comment=None,
):
    """
    修改已有区间型工程调查记录。

    允许修改：
    - draft；
    - completed。

    不允许通过此函数修改：
    - 所属机构；
    - 所属渠系；
    - 业务编号；
    - 调查表类型。
    """

    if not asset_name or not asset_name.strip():
        raise ValueError("工程名称不能为空。")

    record_json = json.dumps(
        record_data,
        ensure_ascii=False,
    )

    with get_connection() as connection:
        record = connection.execute(
            """
            SELECT
                sr.engineering_asset_id,
                sr.record_status,
                sr.project_id,
                sr.survey_batch_id,
                sr.form_version_id,
                sr.organization_unit_id,
                sr.canal_unit_id,

                fd.form_code

            FROM survey_records AS sr

            JOIN form_versions AS fv
                ON sr.form_version_id
                    = fv.id

            JOIN form_definitions AS fd
                ON fv.form_definition_id
                    = fd.id

            WHERE sr.id = ?
              AND fd.form_code = ?
            """,
            (
                survey_record_id,
                form_code,
            ),
        ).fetchone()

        if record is None:
            raise ValueError("没有找到该调查记录。")

        if record["record_status"] not in (
            "draft",
            "completed",
        ):
            raise ValueError("当前记录状态" "不允许直接修改。")

        duplicate = _find_duplicate_range_engineering_survey(
            connection=connection,
            project_id=(record["project_id"]),
            survey_batch_id=(record["survey_batch_id"]),
            form_version_id=(record["form_version_id"]),
            organization_unit_id=(record["organization_unit_id"]),
            canal_unit_id=(record["canal_unit_id"]),
            start_stake_value=(start_stake_value),
            end_stake_value=(end_stake_value),
            exclude_survey_record_id=(survey_record_id),
        )

        if duplicate is not None:
            raise ValueError("当前调查批次中已存在" "相同起止桩号的工程调查记录。")

        engineering_asset_id = record["engineering_asset_id"]

        connection.execute(
            """
            UPDATE engineering_assets
            SET
                asset_name = ?,

                single_stake_text = NULL,
                single_stake_value = NULL,

                start_stake_text = ?,
                start_stake_value = ?,
                end_stake_text = ?,
                end_stake_value = ?,

                updated_at = datetime(
                    'now',
                    'localtime'
                )

            WHERE id = ?
            """,
            (
                asset_name.strip(),
                start_stake_text,
                start_stake_value,
                end_stake_text,
                end_stake_value,
                engineering_asset_id,
            ),
        )

        connection.execute(
            """
            UPDATE survey_records
            SET
                survey_date = ?,
                overall_grade = ?,
                survey_comment = ?,
                record_data_json = ?,

                updated_at = datetime(
                    'now',
                    'localtime'
                )

            WHERE id = ?
            """,
            (
                survey_date,
                overall_grade,
                survey_comment,
                record_json,
                survey_record_id,
            ),
        )

        if inspection_results is not None:
            _replace_inspection_results(
                connection,
                survey_record_id,
                inspection_results,
            )

        return {
            "engineering_asset_id": (engineering_asset_id),
            "survey_record_id": (survey_record_id),
        }


def update_sluice_gate_draft(
    survey_record_id,
    asset_name,
    record_data,
    single_stake_text=None,
    single_stake_value=None,
    inspection_results=None,
    survey_date=None,
    overall_grade=None,
    survey_comment=None,
):
    """
    修改附表2.2水闸调查记录。

    保留原函数作为兼容入口，
    实际修改逻辑统一走点状工程公共函数。
    """

    return update_point_engineering_survey(
        survey_record_id=(survey_record_id),
        form_code="form_2_2",
        asset_name=asset_name,
        record_data=record_data,
        single_stake_text=(single_stake_text),
        single_stake_value=(single_stake_value),
        inspection_results=(inspection_results),
        survey_date=survey_date,
        overall_grade=overall_grade,
        survey_comment=survey_comment,
    )


def complete_sluice_gate_record(
    survey_record_id,
):
    """
    将水闸调查草稿正式标记为 completed。

    完成条件：
    1. 记录必须存在且当前为 draft；
    2. 工程身份信息完整；
    3. 规定的工程基本信息完整；
    4. 结构与材料参数完整；
    5. 14项分项评价全部完成；
    6. 工程状况类别已确定；
    7. 调查时间有效；
    8. 调查意见与建议已填写。

    加固改造年月允许为空。
    """

    with get_connection() as connection:

        record = connection.execute(
            """
            SELECT
                sr.id,
                sr.record_status,
                sr.organization_unit_id,
                sr.canal_unit_id,
                sr.business_code,
                sr.survey_date,
                sr.overall_grade,
                sr.survey_comment,
                sr.record_data_json,

                ea.asset_name

            FROM survey_records AS sr

            LEFT JOIN engineering_assets AS ea
                ON sr.engineering_asset_id = ea.id

            WHERE sr.id = ?
            """,
            (survey_record_id,),
        ).fetchone()

        if record is None:
            raise ValueError("没有找到该调查记录。")

        if record["record_status"] != "draft":
            raise ValueError("只有草稿记录可以执行完成调查。")

        # =========================
        # 解析调查数据
        # =========================

        try:
            record_data = json.loads(record["record_data_json"] or "{}")
        except json.JSONDecodeError:
            raise ValueError("当前调查记录数据异常，" "无法执行完成调查。")

        # =========================
        # 检查必填字段
        # =========================

        missing_fields = []

        def is_missing(value):
            if value is None:
                return True

            if isinstance(value, str):
                return not value.strip()

            return False

        if is_missing(record["asset_name"]):
            missing_fields.append("工程名称")

        if record["organization_unit_id"] is None:
            missing_fields.append("所属水管所")

        if record["canal_unit_id"] is None:
            missing_fields.append("所属渠系")

        if is_missing(record["business_code"]):
            missing_fields.append("业务编号")

        required_record_fields = {
            "stake": "桩号",
            "design_flow": "设计流量",
            "structure_grade": "建筑物等级",
            "build_date": "建成年月",
            "increased_flow": "加大流量",
            "opening_count": "孔数",
            "opening_width": "孔宽",
            "opening_height": "孔高",
            "main_component_material": "主要构件材料",
            "concrete_strength": "混凝土强度",
            "reinforced_concrete_strength": "钢筋混凝土强度",
            "cover_thickness": "保护层厚度",
            "crack_width_limit": "裂缝限宽",
        }

        for field_key, field_name in required_record_fields.items():
            if is_missing(record_data.get(field_key)):
                missing_fields.append(field_name)

        if is_missing(record["survey_date"]):
            missing_fields.append("调查时间")

        if record["overall_grade"] not in (
            "A",
            "B",
            "C",
            "D",
        ):
            missing_fields.append("工程状况类别")

        if is_missing(record["survey_comment"]):
            missing_fields.append("调查意见与建议")

        if missing_fields:
            field_text = "、".join(missing_fields)

            raise ValueError("完成调查前仍有必填内容未填写：" f"{field_text}。")

        # =========================
        # 日期有效性校验
        # =========================

        try:
            datetime.strptime(
                record_data["build_date"],
                "%Y-%m",
            )
        except (TypeError, ValueError):
            raise ValueError("建成年月不是有效的 YYYY-MM 日期。")

        renovation_date = record_data.get("renovation_date")

        if renovation_date:
            try:
                datetime.strptime(
                    renovation_date,
                    "%Y-%m",
                )
            except (TypeError, ValueError):
                raise ValueError("加固改造年月不是有效的 " "YYYY-MM 日期。")

        try:
            datetime.strptime(
                record["survey_date"],
                "%Y-%m-%d",
            )
        except (TypeError, ValueError):
            raise ValueError("调查时间不是有效的 " "YYYY-MM-DD 日期。")

        # =========================
        # 14项分项评价完整性
        # =========================

        inspection_count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM inspection_results
            WHERE survey_record_id = ?
            """,
            (survey_record_id,),
        ).fetchone()["count"]

        if inspection_count != 14:
            raise ValueError(
                "完成调查前必须完成全部14项"
                "分项评价。"
                f"当前已完成 {inspection_count} 项。"
            )

        # =========================
        # 正式完成
        # =========================

        connection.execute(
            """
            UPDATE survey_records
            SET
                record_status = 'completed',
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (survey_record_id,),
        )

        return {
            "survey_record_id": survey_record_id,
            "inspection_count": inspection_count,
        }


def complete_aqueduct_record(
    survey_record_id,
):
    """
    将附表2.3渡槽（座槽）调查草稿
    正式标记为 completed。

    完成条件：
    1. 记录必须属于附表2.3且当前为 draft；
    2. 工程身份信息完整；
    3. 正式基本信息完整；
    4. 12项分项评价全部完成；
    5. 工程状况类别已确定；
    6. 调查时间有效；
    7. 调查意见与建议已填写。

    加固改造年月允许为空。
    """

    with get_connection() as connection:
        record = connection.execute(
            """
            SELECT
                sr.id,
                sr.record_status,
                sr.organization_unit_id,
                sr.canal_unit_id,
                sr.business_code,
                sr.survey_date,
                sr.overall_grade,
                sr.survey_comment,
                sr.record_data_json,

                ea.asset_name,

                fd.form_code

            FROM survey_records AS sr

            LEFT JOIN engineering_assets AS ea
                ON sr.engineering_asset_id = ea.id

            JOIN form_versions AS fv
                ON sr.form_version_id = fv.id

            JOIN form_definitions AS fd
                ON fv.form_definition_id = fd.id

            WHERE sr.id = ?
              AND fd.form_code = 'form_2_3'
            """,
            (survey_record_id,),
        ).fetchone()

        if record is None:
            raise ValueError("没有找到该附表2.3调查记录。")

        if record["record_status"] != "draft":
            raise ValueError("只有草稿记录可以执行完成调查。")

        # =========================
        # 解析调查数据
        # =========================

        try:
            record_data = json.loads(record["record_data_json"] or "{}")
        except json.JSONDecodeError as error:
            raise ValueError("当前调查记录数据异常，" "无法执行完成调查。") from error

        # =========================
        # 检查必填字段
        # =========================

        missing_fields = []

        def is_missing(value):
            if value is None:
                return True

            if isinstance(value, str):
                return not value.strip()

            return False

        if is_missing(record["asset_name"]):
            missing_fields.append("名称")

        if record["organization_unit_id"] is None:
            missing_fields.append("所属水管所")

        if record["canal_unit_id"] is None:
            missing_fields.append("所属渠系")

        if is_missing(record["business_code"]):
            missing_fields.append("业务编号")

        required_record_fields = {
            "stake": "桩号",
            "design_flow": "设计流量",
            "structure_grade": "建筑物等级",
            "build_date": "建成年月",
            "length": "长度",
            "increased_flow": "加大流量",
            "structure_form": "结构形式",
            "section_width": "断面尺寸（宽）",
            "section_height": "断面尺寸（高）",
            "trough_body_structure": "槽身结构",
            "trough_wall_thickness": "槽壁厚度",
            "waterstop_form": "止水形式",
            "trough_bottom_elevation": "槽底高程",
            "span_count": "跨数",
            "lower_support_structure_form": ("下部支撑结构型式"),
        }

        for field_key, field_name in required_record_fields.items():
            if is_missing(record_data.get(field_key)):
                missing_fields.append(field_name)

        if is_missing(record["survey_date"]):
            missing_fields.append("调查时间")

        if record["overall_grade"] not in (
            "A",
            "B",
            "C",
            "D",
        ):
            missing_fields.append("工程状况类别")

        if is_missing(record["survey_comment"]):
            missing_fields.append("调查意见与建议")

        if missing_fields:
            field_text = "、".join(missing_fields)

            raise ValueError("完成调查前仍有必填内容未填写：" f"{field_text}。")

        # =========================
        # 日期有效性
        # =========================

        try:
            datetime.strptime(
                record_data["build_date"],
                "%Y-%m",
            )
        except (TypeError, ValueError) as error:
            raise ValueError("建成年月不是有效的 " "YYYY-MM 日期。") from error

        renovation_date = record_data.get("renovation_date")

        if renovation_date:
            try:
                datetime.strptime(
                    renovation_date,
                    "%Y-%m",
                )
            except (
                TypeError,
                ValueError,
            ) as error:
                raise ValueError("加固改造年月不是有效的 " "YYYY-MM 日期。") from error

        try:
            datetime.strptime(
                record["survey_date"],
                "%Y-%m-%d",
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise ValueError("调查时间不是有效的 " "YYYY-MM-DD 日期。") from error

        # =========================
        # 12项分项评价
        # =========================

        inspection_count = connection.execute(
            """
                SELECT COUNT(*) AS count
                FROM inspection_results
                WHERE survey_record_id = ?
                """,
            (survey_record_id,),
        ).fetchone()["count"]

        if inspection_count != 12:
            raise ValueError(
                "完成调查前必须完成全部12项"
                "分项评价。"
                f"当前已完成 "
                f"{inspection_count} 项。"
            )

        # =========================
        # 正式完成
        # =========================

        connection.execute(
            """
            UPDATE survey_records
            SET
                record_status = 'completed',
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (survey_record_id,),
        )

        return {
            "survey_record_id": (survey_record_id),
            "inspection_count": (inspection_count),
        }


def complete_inverted_siphon_record(
    survey_record_id,
):
    """
    将附表2.4倒虹吸调查草稿
    正式标记为 completed。

    完成条件：
    1. 记录必须属于附表2.4且当前为 draft；
    2. 工程身份信息完整；
    3. 正式基本信息完整；
    4. 12项分项评价全部完成；
    5. 工程状况类别已确定；
    6. 调查时间有效；
    7. 调查意见与建议已填写。

    加固改造年月允许为空。
    """

    with get_connection() as connection:
        record = connection.execute(
            """
            SELECT
                sr.id,
                sr.record_status,
                sr.organization_unit_id,
                sr.canal_unit_id,
                sr.business_code,
                sr.survey_date,
                sr.overall_grade,
                sr.survey_comment,
                sr.record_data_json,

                ea.asset_name,

                fd.form_code

            FROM survey_records AS sr

            LEFT JOIN engineering_assets AS ea
                ON sr.engineering_asset_id = ea.id

            JOIN form_versions AS fv
                ON sr.form_version_id = fv.id

            JOIN form_definitions AS fd
                ON fv.form_definition_id = fd.id

            WHERE sr.id = ?
              AND fd.form_code = 'form_2_4'
            """,
            (survey_record_id,),
        ).fetchone()

        if record is None:
            raise ValueError("没有找到该附表2.4调查记录。")

        if record["record_status"] != "draft":
            raise ValueError("只有草稿记录可以执行完成调查。")

        try:
            record_data = json.loads(record["record_data_json"] or "{}")
        except json.JSONDecodeError as error:
            raise ValueError("当前调查记录数据异常，" "无法执行完成调查。") from error

        missing_fields = []

        def is_missing(value):
            if value is None:
                return True

            if isinstance(value, str):
                return not value.strip()

            return False

        # 工程身份
        if is_missing(record["asset_name"]):
            missing_fields.append("名称")

        if record["organization_unit_id"] is None:
            missing_fields.append("所属水管所")

        if record["canal_unit_id"] is None:
            missing_fields.append("所属渠系")

        if is_missing(record["business_code"]):
            missing_fields.append("业务编号")

        # 正式基本信息
        required_record_fields = {
            "stake": "桩号",
            "design_flow": "设计流量",
            "structure_grade": "建筑物等级",
            "build_date": "建成年月",
            "length": "长度",
            "increased_flow": "加大流量",
            "structure_form": "结构形式",
            "section_size": "尺寸",
            "pipe_body_structure": "管身结构",
            "wall_thickness": "壁厚度",
            "waterstop_form": "止水形式",
            "channel_bottom_elevation": "渠底高程",
        }

        for field_key, field_name in required_record_fields.items():
            if is_missing(record_data.get(field_key)):
                missing_fields.append(field_name)

        if is_missing(record["survey_date"]):
            missing_fields.append("调查时间")

        if record["overall_grade"] not in (
            "A",
            "B",
            "C",
            "D",
        ):
            missing_fields.append("工程状况类别")

        if is_missing(record["survey_comment"]):
            missing_fields.append("调查意见与建议")

        if missing_fields:
            field_text = "、".join(missing_fields)

            raise ValueError("完成调查前仍有必填内容未填写：" f"{field_text}。")

        # 日期有效性
        try:
            datetime.strptime(
                record_data["build_date"],
                "%Y-%m",
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise ValueError("建成年月不是有效的 " "YYYY-MM 日期。") from error

        renovation_date = record_data.get("renovation_date")

        if renovation_date:
            try:
                datetime.strptime(
                    renovation_date,
                    "%Y-%m",
                )
            except (
                TypeError,
                ValueError,
            ) as error:
                raise ValueError("加固改造年月不是有效的 " "YYYY-MM 日期。") from error

        try:
            datetime.strptime(
                record["survey_date"],
                "%Y-%m-%d",
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise ValueError("调查时间不是有效的 " "YYYY-MM-DD 日期。") from error

        # 12项分项评价
        inspection_count = connection.execute(
            """
                SELECT COUNT(*) AS count
                FROM inspection_results
                WHERE survey_record_id = ?
                """,
            (survey_record_id,),
        ).fetchone()["count"]

        if inspection_count != 12:
            raise ValueError(
                "完成调查前必须完成全部12项"
                "分项评价。"
                f"当前已完成 "
                f"{inspection_count} 项。"
            )

        connection.execute(
            """
            UPDATE survey_records
            SET
                record_status = 'completed',
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (survey_record_id,),
        )

        return {
            "survey_record_id": (survey_record_id),
            "inspection_count": (inspection_count),
        }


def complete_tunnel_record(
    survey_record_id,
):
    """
    将附表2.5隧洞调查草稿
    正式标记为 completed。

    完成条件：
    1. 必须属于附表2.5；
    2. 当前必须为 draft；
    3. 工程身份和起止桩号完整；
    4. 正式基本信息完整；
    5. 13项分项评价全部完成；
    6. 工程状况类别已确定；
    7. 调查时间有效；
    8. 调查意见与建议已填写。

    加固改造年月允许为空。
    """

    with get_connection() as connection:
        record = connection.execute(
            """
            SELECT
                sr.id,
                sr.record_status,
                sr.organization_unit_id,
                sr.canal_unit_id,
                sr.business_code,
                sr.survey_date,
                sr.overall_grade,
                sr.survey_comment,
                sr.record_data_json,

                ea.asset_name,
                ea.start_stake_text,
                ea.start_stake_value,
                ea.end_stake_text,
                ea.end_stake_value,

                fd.form_code

            FROM survey_records AS sr

            JOIN engineering_assets AS ea
                ON sr.engineering_asset_id
                    = ea.id

            JOIN form_versions AS fv
                ON sr.form_version_id
                    = fv.id

            JOIN form_definitions AS fd
                ON fv.form_definition_id
                    = fd.id

            WHERE sr.id = ?
              AND fd.form_code = 'form_2_5'
            """,
            (survey_record_id,),
        ).fetchone()

        if record is None:
            raise ValueError(
                "没有找到该附表2.5调查记录。"
            )

        if record["record_status"] != "draft":
            raise ValueError(
                "只有草稿记录可以执行完成调查。"
            )

        try:
            record_data = json.loads(
                record["record_data_json"]
                or "{}"
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                "当前调查记录数据异常，"
                "无法执行完成调查。"
            ) from error

        missing_fields = []

        def is_missing(value):
            if value is None:
                return True

            if isinstance(value, str):
                return not value.strip()

            return False

        # =====================================================
        # 工程身份
        # =====================================================

        if is_missing(record["asset_name"]):
            missing_fields.append("名称")

        if record["organization_unit_id"] is None:
            missing_fields.append(
                "所属水管所"
            )

        if record["canal_unit_id"] is None:
            missing_fields.append(
                "所属渠系"
            )

        if is_missing(record["business_code"]):
            missing_fields.append(
                "业务编号"
            )

        if is_missing(
            record["start_stake_text"]
        ):
            missing_fields.append(
                "起始桩号"
            )

        if is_missing(
            record["end_stake_text"]
        ):
            missing_fields.append(
                "终止桩号"
            )

        # =====================================================
        # 正式基本信息
        # =====================================================

        required_record_fields = {
            "design_flow": "设计流量",
            "structure_grade": "建筑物等级",
            "build_date": "建成年月",
            "length": "长度",
            "increased_flow": "加大流量",
            "lining_form": "衬砌形式",
            "lining_thickness": "衬砌厚度",
            "concrete_strength": "混凝土强度",
            "inlet_outlet_bottom_elevation": (
                "进出口底部高程"
            ),
            "longitudinal_slope": (
                "纵坡（n/1000）"
            ),
            "section_form": "断面型式",
            "section_width": "尺寸（宽）",
            "section_height": "尺寸（高）",
            "cover_thickness": (
                "钢筋保护层厚度"
            ),
        }

        for field_key, field_name in (
            required_record_fields.items()
        ):
            if is_missing(
                record_data.get(field_key)
            ):
                missing_fields.append(
                    field_name
                )

        if is_missing(
            record["survey_date"]
        ):
            missing_fields.append(
                "调查时间"
            )

        if record["overall_grade"] not in (
            "A",
            "B",
            "C",
            "D",
        ):
            missing_fields.append(
                "工程状况类别"
            )

        if is_missing(
            record["survey_comment"]
        ):
            missing_fields.append(
                "调查意见与建议"
            )

        if missing_fields:
            raise ValueError(
                "完成调查前仍有必填内容未填写："
                + "、".join(missing_fields)
                + "。"
            )

        # =====================================================
        # 桩号逻辑
        # =====================================================

        if (
            record["start_stake_value"]
            is not None
            and record["end_stake_value"]
            is not None
            and record["end_stake_value"]
            < record["start_stake_value"]
        ):
            raise ValueError(
                "终止桩号不能小于起始桩号。"
            )

        # =====================================================
        # 日期
        # =====================================================

        try:
            datetime.strptime(
                record_data["build_date"],
                "%Y-%m",
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise ValueError(
                "建成年月不是有效的 "
                "YYYY-MM 日期。"
            ) from error

        renovation_date = (
            record_data.get(
                "renovation_date"
            )
        )

        if renovation_date:
            try:
                datetime.strptime(
                    renovation_date,
                    "%Y-%m",
                )
            except (
                TypeError,
                ValueError,
            ) as error:
                raise ValueError(
                    "加固改造年月不是有效的 "
                    "YYYY-MM 日期。"
                ) from error

        try:
            datetime.strptime(
                record["survey_date"],
                "%Y-%m-%d",
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise ValueError(
                "调查时间不是有效的 "
                "YYYY-MM-DD 日期。"
            ) from error

        # =====================================================
        # 13项评价
        # =====================================================

        inspection_count = (
            connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM inspection_results
                WHERE survey_record_id = ?
                """,
                (survey_record_id,),
            ).fetchone()["count"]
        )

        if inspection_count != 13:
            raise ValueError(
                "完成调查前必须完成全部13项"
                "分项评价。"
                f"当前已完成 "
                f"{inspection_count} 项。"
            )

        connection.execute(
            """
            UPDATE survey_records
            SET
                record_status = 'completed',
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (survey_record_id,),
        )

        return {
            "survey_record_id": (
                survey_record_id
            ),
            "inspection_count": (
                inspection_count
            ),
        }
    

def get_engineering_assets(
    project_id,
    survey_batch_id=None,
):
    """
    获取工程台账。

    EngineeringAsset 是长期工程对象。
    如果提供 survey_batch_id，
    同时带出该工程在当前调查批次中的调查状态。
    """

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                ea.id AS engineering_asset_id,
                ea.business_code,
                ea.asset_name,
                ea.asset_type,

                ea.single_stake_text,
                ea.start_stake_text,
                ea.end_stake_text,

                ea.status AS asset_status,
                ea.created_at,

                office.name AS office_name,
                department.name AS department_name,

                canal.name AS canal_name,
                canal.canal_level,

                first_batch.batch_name
                    AS first_batch_name,

                (
                    SELECT sr.record_status
                    FROM survey_records AS sr
                    WHERE sr.engineering_asset_id = ea.id
                    AND (
                            ? IS NULL
                            OR sr.survey_batch_id = ?
                    )
                    AND sr.record_status != 'void'
                    ORDER BY sr.id DESC
                    LIMIT 1
                ) AS survey_status,

                (
                    SELECT sr.overall_grade
                    FROM survey_records AS sr
                    WHERE sr.engineering_asset_id = ea.id
                    AND (
                            ? IS NULL
                            OR sr.survey_batch_id = ?
                        )
                    AND sr.record_status != 'void'
                    ORDER BY sr.id DESC
                    LIMIT 1
                ) AS overall_grade

            FROM engineering_assets AS ea

            LEFT JOIN organization_units AS office
                ON ea.organization_unit_id = office.id

            LEFT JOIN organization_units AS department
                ON office.parent_id = department.id

            LEFT JOIN canal_units AS canal
                ON ea.canal_unit_id = canal.id

            LEFT JOIN survey_batches AS first_batch
                ON ea.first_survey_batch_id = first_batch.id

            WHERE ea.project_id = ?

            ORDER BY
                ea.business_code,
                ea.id
            """,
            (
                survey_batch_id,
                survey_batch_id,
                survey_batch_id,
                survey_batch_id,
                project_id,
            ),
        ).fetchall()

        return rows


def get_engineering_asset_detail(
    engineering_asset_id,
):
    """
    获取单个长期工程对象的基本信息。
    """

    with get_connection() as connection:
        return connection.execute(
            """
            SELECT
                ea.id AS engineering_asset_id,
                ea.business_code,
                ea.asset_name,
                ea.asset_type,

                ea.single_stake_text,
                ea.single_stake_value,

                ea.start_stake_text,
                ea.start_stake_value,

                ea.end_stake_text,
                ea.end_stake_value,

                ea.status AS asset_status,
                ea.code_scheme_version,
                ea.notes,
                ea.created_at,
                ea.updated_at,

                office.name AS office_name,
                department.name AS department_name,

                canal.name AS canal_name,
                canal.canal_level,

                first_batch.batch_name
                    AS first_batch_name

            FROM engineering_assets AS ea

            LEFT JOIN organization_units AS office
                ON ea.organization_unit_id = office.id

            LEFT JOIN organization_units AS department
                ON office.parent_id = department.id

            LEFT JOIN canal_units AS canal
                ON ea.canal_unit_id = canal.id

            LEFT JOIN survey_batches AS first_batch
                ON ea.first_survey_batch_id = first_batch.id

            WHERE ea.id = ?
            """,
            (engineering_asset_id,),
        ).fetchone()


def get_engineering_asset_history(
    engineering_asset_id,
):
    """
    获取某个工程对象的历次调查记录。
    """

    with get_connection() as connection:
        return connection.execute(
            """
            SELECT
                sr.id AS survey_record_id,
                sr.business_code,
                sr.survey_date,
                sr.overall_grade,
                sr.record_status,
                sr.created_at,
                sr.updated_at,

                sb.batch_name,
                sb.batch_code,

                fd.form_number,
                fd.form_name,

                fv.version_code,
                fv.version_name

            FROM survey_records AS sr

            JOIN survey_batches AS sb
                ON sr.survey_batch_id = sb.id

            JOIN form_versions AS fv
                ON sr.form_version_id = fv.id

            JOIN form_definitions AS fd
                ON fv.form_definition_id = fd.id

            WHERE sr.engineering_asset_id = ?

            ORDER BY
                sb.id DESC,
                sr.id DESC
            """,
            (engineering_asset_id,),
        ).fetchall()


def get_current_context():
    """
    获取当前启用的项目和当前调查批次。

    当前 V0.1 规则：
    - 取第一个处于 active 状态的项目；
    - 在该项目下取最新一个 active 调查批次。
    """

    with get_connection() as connection:
        project = connection.execute("""
            SELECT *
            FROM projects
            WHERE status = 'active'
            ORDER BY id
            LIMIT 1
            """).fetchone()

        if project is None:
            return None

        batch = connection.execute(
            """
            SELECT *
            FROM survey_batches
            WHERE project_id = ?
            AND status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """,
            (project["id"],),
        ).fetchone()

        return {
            "project_id": project["id"],
            "project_name": project["name"],
            "project_short_name": project["short_name"],
            "batch_id": batch["id"] if batch else None,
            "batch_name": batch["batch_name"] if batch else None,
            "batch_code": batch["batch_code"] if batch else None,
        }


def get_survey_readiness():
    """
    检查当前环境是否具备开始工程调查的基本条件。

    当前检查：
    1. 当前项目
    2. 当前调查批次
    3. 至少一个启用的基层处
    4. 至少一个属于启用基层处的启用水管所
    5. 至少一条启用渠系

    返回示例：
    {
        "ready": True,
        "missing": [],
        "department_count": 2,
        "office_count": 5,
        "canal_count": 12,
    }
    """

    missing = []

    context = get_current_context()

    if context is None:
        missing.append("当前项目和调查批次")

        return {
            "ready": False,
            "missing": missing,
            "department_count": 0,
            "office_count": 0,
            "canal_count": 0,
        }

    project_id = context.get("project_id")
    batch_id = context.get("batch_id")

    if project_id is None:
        missing.append("当前项目")

    if batch_id is None:
        missing.append("当前调查批次")

    with get_connection() as connection:

        # =========================
        # 基层处
        # =========================

        department_row = connection.execute("""
                SELECT COUNT(*) AS count
                FROM organization_units
                WHERE unit_type = 'department'
                  AND status = 'active'
                """).fetchone()

        department_count = (
            int(department_row["count"]) if department_row is not None else 0
        )

        if department_count == 0:
            missing.append("至少一个启用的基层处")

        # =========================
        # 水管所
        # =========================
        #
        # 不只是检查 water_office 本身启用，
        # 还要求它所属的基层处处于启用状态。

        office_row = connection.execute("""
            SELECT COUNT(*) AS count
            FROM organization_units AS office
            JOIN organization_units AS department
              ON department.id = office.parent_id
            WHERE office.unit_type = 'water_office'
              AND office.status = 'active'
              AND department.unit_type = 'department'
              AND department.status = 'active'
            """).fetchone()

        office_count = int(office_row["count"]) if office_row is not None else 0

        if office_count == 0:
            missing.append("至少一个启用的水管所")

        # =========================
        # 渠系
        # =========================

        canal_row = connection.execute("""
            SELECT COUNT(*) AS count
            FROM canal_units
            WHERE status = 'active'
            """).fetchone()

        canal_count = int(canal_row["count"]) if canal_row is not None else 0

        if canal_count == 0:
            missing.append("至少一条启用的渠系")

    return {
        "ready": len(missing) == 0,
        "missing": missing,
        "department_count": department_count,
        "office_count": office_count,
        "canal_count": canal_count,
    }


def show_database_info():
    """
    在终端显示当前数据库中的项目和调查批次，
    用于开发阶段检查。
    """

    with get_connection() as connection:

        projects = connection.execute("""
            SELECT *
            FROM projects
            ORDER BY id
            """).fetchall()

        batches = connection.execute("""
            SELECT *
            FROM survey_batches
            ORDER BY id
            """).fetchall()

        print(f"数据库位置：{DB_PATH}")
        print()

        print("项目：")
        for project in projects:
            print(
                f"  {project['id']} | " f"{project['name']} | " f"{project['status']}"
            )

        print()

        print("调查批次：")
        for batch in batches:
            print(
                f"  {batch['id']} | " f"{batch['batch_name']} | " f"{batch['status']}"
            )


if __name__ == "__main__":
    init_database()
    create_demo_data()
    show_database_info()
