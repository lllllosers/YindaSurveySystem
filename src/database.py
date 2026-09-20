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


# =============================================================
# 跨数据库稳定身份
# =============================================================
#
# SQLite 自增 id 只在当前数据库内有效。
# 任务包 / 结果包 / 多数据库合并必须使用稳定 UID。
#
# 这里为后续需要跨数据库传递的核心实体建立 UID：
# - Project
# - SurveyBatch
# - OrganizationUnit
# - CanalUnit
# - EngineeringAsset
# - SurveyRecord
#
# SurveyMedia 已经拥有 media_uid；
# InspectionResult 使用
# (survey_record_uid, item_code) 作为稳定业务身份，
# 因此暂不额外增加独立 UID。
# =============================================================

_STABLE_IDENTITY_SPECS = (
    (
        "projects",
        "project_uid",
    ),
    (
        "survey_batches",
        "survey_batch_uid",
    ),
    (
        "organization_units",
        "organization_unit_uid",
    ),
    (
        "canal_units",
        "canal_unit_uid",
    ),
    (
        "engineering_assets",
        "engineering_asset_uid",
    ),
    (
        "survey_records",
        "survey_record_uid",
    ),
)


def _ensure_stable_identity_schema(
    connection,
):
    """
    对既有数据库执行可重复的稳定身份迁移。

    兼容旧数据库：
    1. 缺少 UID 列时通过 ALTER TABLE 增加；
    2. 为历史记录回填 32 位随机十六进制 UID；
    3. 建立唯一索引；
    4. 为后续 INSERT 自动生成 UID；
    5. UID 一旦生成后禁止修改。

    不重建业务表，不改变现有整数主键和外键。
    """

    for (
        table_name,
        uid_column,
    ) in _STABLE_IDENTITY_SPECS:
        columns = {
            row["name"]
            for row in (
                connection.execute(
                    (
                        "PRAGMA table_info("
                        f"{table_name}"
                        ")"
                    )
                ).fetchall()
            )
        }

        if uid_column not in columns:
            connection.execute(
                (
                    f"ALTER TABLE {table_name} "
                    f"ADD COLUMN {uid_column} TEXT"
                )
            )

        connection.execute(
            (
                f"UPDATE {table_name} "
                f"SET {uid_column} = "
                "lower(hex(randomblob(16))) "
                f"WHERE {uid_column} IS NULL "
                f"OR trim({uid_column}) = ''"
            )
        )

        duplicate = connection.execute(
            (
                f"SELECT {uid_column}, "
                "COUNT(*) AS count_value "
                f"FROM {table_name} "
                f"WHERE {uid_column} IS NOT NULL "
                f"AND trim({uid_column}) <> '' "
                f"GROUP BY {uid_column} "
                "HAVING COUNT(*) > 1 "
                "LIMIT 1"
            )
        ).fetchone()

        if duplicate is not None:
            raise RuntimeError(
                (
                    f"{table_name}.{uid_column} "
                    "存在重复稳定 UID，"
                    "数据库身份迁移已停止。"
                )
            )

        index_name = (
            f"uq_{table_name}_"
            f"{uid_column}"
        )

        connection.execute(
            (
                "CREATE UNIQUE INDEX "
                f"IF NOT EXISTS {index_name} "
                f"ON {table_name} "
                f"({uid_column})"
            )
        )

        insert_trigger = (
            f"trg_{table_name}_"
            f"{uid_column}_insert"
        )

        immutable_trigger = (
            f"trg_{table_name}_"
            f"{uid_column}_immutable"
        )

        connection.executescript(
            f"""
            CREATE TRIGGER IF NOT EXISTS
                {insert_trigger}
            AFTER INSERT ON {table_name}
            FOR EACH ROW
            WHEN
                NEW.{uid_column} IS NULL
                OR trim(NEW.{uid_column}) = ''
            BEGIN
                UPDATE {table_name}
                SET
                    {uid_column}
                    = lower(
                        hex(
                            randomblob(16)
                        )
                    )
                WHERE id = NEW.id;
            END;

            CREATE TRIGGER IF NOT EXISTS
                {immutable_trigger}
            BEFORE UPDATE OF {uid_column}
            ON {table_name}
            FOR EACH ROW
            WHEN
                OLD.{uid_column} IS NOT NULL
                AND trim(
                    OLD.{uid_column}
                ) <> ''
                AND OLD.{uid_column}
                    IS NOT NEW.{uid_column}
            BEGIN
                SELECT RAISE(
                    ABORT,
                    '{uid_column} is immutable'
                );
            END;
            """
        )


# =============================================================
# 甲方正式组织机构 / 渠系主数据
# =============================================================

def _ensure_official_master_data_schema(
    connection,
):
    """
    为正式主数据增加可追踪、可排序、可重复初始化的字段。

    不把名称本身当作永久身份：
    - master_key：官方种子内部稳定键；
    - sort_order：正式展示/后续任务范围排序；
    - source_sequence：甲方新表 1~63 序号；
    - management_note：甲方新表“备注”原文。

    这些字段不替代 Stage 08 的跨数据库 UID。
    """

    organization_columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(organization_units)"
        ).fetchall()
    }

    if "master_key" not in organization_columns:
        connection.execute(
            """
            ALTER TABLE organization_units
            ADD COLUMN master_key TEXT
            """
        )

    if "sort_order" not in organization_columns:
        connection.execute(
            """
            ALTER TABLE organization_units
            ADD COLUMN sort_order INTEGER
            NOT NULL DEFAULT 0
            """
        )

    canal_columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(canal_units)"
        ).fetchall()
    }

    if "master_key" not in canal_columns:
        connection.execute(
            """
            ALTER TABLE canal_units
            ADD COLUMN master_key TEXT
            """
        )

    if "sort_order" not in canal_columns:
        connection.execute(
            """
            ALTER TABLE canal_units
            ADD COLUMN sort_order INTEGER
            NOT NULL DEFAULT 0
            """
        )

    connection.executescript(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
            uq_organization_units_master_key
        ON organization_units(master_key)
        WHERE master_key IS NOT NULL;

        CREATE UNIQUE INDEX IF NOT EXISTS
            uq_canal_units_master_key
        ON canal_units(master_key)
        WHERE master_key IS NOT NULL;

        CREATE INDEX IF NOT EXISTS
            idx_organization_units_sort_order
        ON organization_units(
            sort_order,
            id
        );

        CREATE INDEX IF NOT EXISTS
            idx_canal_units_sort_order
        ON canal_units(
            sort_order,
            id
        );

        CREATE TABLE IF NOT EXISTS
            master_data_seed_history (
                seed_key TEXT PRIMARY KEY,
                source_description TEXT NOT NULL,
                details_json TEXT NOT NULL
                    DEFAULT '{}',
                applied_at TEXT NOT NULL
                    DEFAULT (
                        datetime(
                            'now',
                            'localtime'
                        )
                    )
            );
        """
    )



_CANAL_UNIT_LEGACY_OWNER_COLUMN = (
    "organization_unit_id"
)

_CANAL_UNIT_REBUILD_TABLE = (
    "canal_units__physical_schema_v2"
)

_CANAL_UNIT_KNOWN_SCHEMA_OBJECTS = {
    "uq_canal_units_canal_unit_uid",
    "trg_canal_units_canal_unit_uid_insert",
    "trg_canal_units_canal_unit_uid_immutable",
    "uq_canal_units_master_key",
    "idx_canal_units_sort_order",
}


_STALE_TASK_WORKSPACE_TABLE = (
    "survey_task_workspace_canals"
)

_KNOWN_TASK_SCOPE_TRIGGER_NAMES = {
    "trg_survey_records_task_scope_insert",
    "trg_survey_records_task_source_insert",
    "trg_survey_records_task_scope_update",
    "trg_survey_records_source_task_uid_immutable",
    "trg_survey_records_source_management_scope_uid_immutable",
}


def _drop_stale_task_scope_triggers(
    connection,
):
    """
    删除仍引用已退役 workspace_canals 表的已知任务约束触发器。

    这是数据库结构迁移前的窄范围修复：
    - 只检查 trigger SQL 中明确引用旧表名的触发器；
    - 只允许删除当前版本已知的任务触发器名称；
    - 遇到未知触发器时拒绝迁移，不做猜测；
    - 当前版本触发器引用 workspace_scopes，不会被删除。

    应用 bootstrap 后续会由
    ensure_survey_task_record_scope_schema()
    重新建立当前版本触发器。
    """

    rows = connection.execute(
        """
        SELECT
            name,
            sql
        FROM sqlite_master
        WHERE type = 'trigger'
          AND sql IS NOT NULL
          AND instr(
                lower(sql),
                lower(?)
              ) > 0
        ORDER BY name
        """,
        (
            _STALE_TASK_WORKSPACE_TABLE,
        ),
    ).fetchall()

    if not rows:
        return ()

    unknown = [
        str(
            row["name"]
        )
        for row in rows
        if row["name"]
        not in _KNOWN_TASK_SCOPE_TRIGGER_NAMES
    ]

    if unknown:
        raise RuntimeError(
            "检测到引用已退役任务工作区表的"
            "未知触发器："
            + "、".join(
                unknown
            )
            + "。为避免误删自定义数据库逻辑，"
            "本次 schema 迁移已停止。"
        )

    removed = []

    for row in rows:
        trigger_name = str(
            row["name"]
        )

        # trigger_name 已通过固定白名单验证。
        connection.execute(
            (
                'DROP TRIGGER IF EXISTS "'
                + trigger_name
                + '"'
            )
        )

        removed.append(
            trigger_name
        )

    return tuple(
        removed
    )


def _ensure_canal_unit_physical_schema(
    connection,
):
    """
    将既有 canal_units 收口为纯物理渠道表。

    当前版本不再允许 CanalUnit 保存管理单位归属。
    对仍带 organization_unit_id 的开发阶段数据库：
    1. 先确认旧归属已经存在等价 CanalManagementScope；
    2. 拒绝存在未知 canal_units 索引/触发器的数据库；
    3. 在单个 SQLite 事务内重建 canal_units；
    4. 保留 ID、层级、状态、稳定 UID、master_key 和排序；
    5. 事务提交前执行 foreign_key_check。

    新数据库已经使用目标 schema，因此本函数直接返回。
    """

    columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(canal_units)"
        ).fetchall()
    }

    if (
        _CANAL_UNIT_LEGACY_OWNER_COLUMN
        not in columns
    ):
        return {
            "rebuilt": False,
            "legacy_assignment_count": 0,
        }

    required_columns = {
        "id",
        "parent_id",
        "name",
        "canal_level",
        "status",
        "description",
        "created_at",
        "updated_at",
    }

    missing_required = sorted(
        required_columns - columns
    )

    if missing_required:
        raise RuntimeError(
            "canal_units 结构不完整，"
            "无法安全执行物理 schema 收口："
            + "、".join(missing_required)
            + "。"
        )

    schema_objects = connection.execute(
        """
        SELECT
            type,
            name
        FROM sqlite_master
        WHERE tbl_name = 'canal_units'
          AND type IN ('index', 'trigger')
          AND sql IS NOT NULL
        ORDER BY type, name
        """
    ).fetchall()

    unknown_objects = [
        (
            str(row["type"]),
            str(row["name"]),
        )
        for row in schema_objects
        if row["name"]
        not in _CANAL_UNIT_KNOWN_SCHEMA_OBJECTS
    ]

    if unknown_objects:
        object_text = "、".join(
            f"{object_type}:{object_name}"
            for (
                object_type,
                object_name,
            )
            in unknown_objects
        )

        raise RuntimeError(
            "canal_units 存在当前版本"
            "无法自动重建的未知索引/触发器："
            f"{object_text}。"
        )

    legacy_assignment_count = int(
        connection.execute(
            """
            SELECT COUNT(*) AS value
            FROM canal_units
            WHERE organization_unit_id
                IS NOT NULL
            """
        ).fetchone()["value"]
    )

    if legacy_assignment_count:
        scope_table_exists = (
            connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name =
                    'canal_management_scopes'
                """
            ).fetchone()
            is not None
        )

        if not scope_table_exists:
            raise RuntimeError(
                "检测到 canal_units 中仍有"
                "旧管理单位数据，但数据库尚未建立"
                " CanalManagementScope。"
                "为避免丢失管理关系，"
                "本次 schema 迁移已停止。"
            )

        unmatched = connection.execute(
            """
            SELECT
                canal.id,
                canal.name,
                canal.organization_unit_id
            FROM canal_units AS canal
            WHERE
                canal.organization_unit_id
                    IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1
                    FROM canal_management_scopes
                        AS cms
                    WHERE
                        cms.canal_unit_id
                            = canal.id
                        AND
                        cms.organization_unit_id
                            = canal.organization_unit_id
                )
            ORDER BY canal.id
            LIMIT 10
            """
        ).fetchall()

        if unmatched:
            details = "；".join(
                (
                    f"ID={row['id']} "
                    f"{row['name']} -> 组织ID "
                    f"{row['organization_unit_id']}"
                )
                for row in unmatched
            )

            raise RuntimeError(
                "检测到尚未迁移到 "
                "CanalManagementScope 的"
                "旧渠道管理关系："
                f"{details}。"
                "为避免数据丢失，"
                "本次 schema 迁移已停止。"
            )

    source_expressions = {
        "canal_unit_uid": (
            "canal_unit_uid"
            if "canal_unit_uid" in columns
            else "NULL"
        ),
        "master_key": (
            "master_key"
            if "master_key" in columns
            else "NULL"
        ),
        "sort_order": (
            "COALESCE(sort_order, 0)"
            if "sort_order" in columns
            else "0"
        ),
    }

    row_count_before = int(
        connection.execute(
            """
            SELECT COUNT(*) AS value
            FROM canal_units
            """
        ).fetchone()["value"]
    )

    original_foreign_keys = int(
        connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]
    )

    if connection.in_transaction:
        connection.commit()

    connection.execute(
        "PRAGMA foreign_keys = OFF"
    )

    if int(
        connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]
    ) != 0:
        raise RuntimeError(
            "SQLite 未能临时关闭 foreign_keys，"
            "无法安全重建 canal_units。"
        )

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        # SQLite ALTER TABLE RENAME 会重新解析数据库 schema。
        # 若历史 trigger 仍引用已经删除的
        # survey_task_workspace_canals，会导致与 CanalUnit
        # 无关的 rename 也失败，因此先在同一事务内清掉
        # 这些已知陈旧 trigger。
        _drop_stale_task_scope_triggers(
            connection
        )

        connection.execute(
            f"""
            DROP TABLE IF EXISTS
                {_CANAL_UNIT_REBUILD_TABLE}
            """
        )

        connection.execute(
            f"""
            CREATE TABLE
                {_CANAL_UNIT_REBUILD_TABLE} (
                    id INTEGER PRIMARY KEY
                        AUTOINCREMENT,

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

                    status TEXT NOT NULL
                        DEFAULT 'active'
                        CHECK (
                            status IN (
                                'active',
                                'inactive'
                            )
                        ),

                    description TEXT,

                    created_at TEXT NOT NULL
                        DEFAULT (
                            datetime(
                                'now',
                                'localtime'
                            )
                        ),

                    updated_at TEXT NOT NULL
                        DEFAULT (
                            datetime(
                                'now',
                                'localtime'
                            )
                        ),

                    canal_unit_uid TEXT,
                    master_key TEXT,

                    sort_order INTEGER
                        NOT NULL DEFAULT 0,

                    FOREIGN KEY (parent_id)
                        REFERENCES
                            {_CANAL_UNIT_REBUILD_TABLE}(id)
                )
            """
        )

        connection.execute(
            f"""
            INSERT INTO
                {_CANAL_UNIT_REBUILD_TABLE} (
                    id,
                    parent_id,
                    name,
                    canal_level,
                    status,
                    description,
                    created_at,
                    updated_at,
                    canal_unit_uid,
                    master_key,
                    sort_order
                )
            SELECT
                id,
                parent_id,
                name,
                canal_level,
                status,
                description,
                created_at,
                updated_at,
                {source_expressions['canal_unit_uid']},
                {source_expressions['master_key']},
                {source_expressions['sort_order']}
            FROM canal_units
            ORDER BY id
            """
        )

        row_count_after_copy = int(
            connection.execute(
                f"""
                SELECT COUNT(*) AS value
                FROM {_CANAL_UNIT_REBUILD_TABLE}
                """
            ).fetchone()["value"]
        )

        if (
            row_count_after_copy
            != row_count_before
        ):
            raise RuntimeError(
                "canal_units 重建复制行数不一致，"
                "迁移已回滚。"
            )

        connection.execute(
            "DROP TABLE canal_units"
        )

        connection.execute(
            f"""
            ALTER TABLE
                {_CANAL_UNIT_REBUILD_TABLE}
            RENAME TO canal_units
            """
        )

        migrated_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(canal_units)"
            ).fetchall()
        }

        if (
            _CANAL_UNIT_LEGACY_OWNER_COLUMN
            in migrated_columns
        ):
            raise RuntimeError(
                "canal_units 旧管理字段"
                "仍然存在，迁移已回滚。"
            )

        parent_foreign_keys = [
            dict(row)
            for row in connection.execute(
                "PRAGMA foreign_key_list(canal_units)"
            ).fetchall()
        ]

        invalid_parent_fk = [
            row
            for row in parent_foreign_keys
            if (
                row["from"] == "parent_id"
                and row["table"]
                != "canal_units"
            )
        ]

        if invalid_parent_fk:
            raise RuntimeError(
                "canal_units 自引用外键"
                "在重建后指向异常，"
                "迁移已回滚。"
            )

        foreign_key_violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if foreign_key_violations:
            preview = "；".join(
                (
                    f"{row[0]} rowid={row[1]} "
                    f"parent={row[2]}"
                )
                for row in foreign_key_violations[:10]
            )

            raise RuntimeError(
                "canal_units 重建后"
                "外键一致性检查失败："
                f"{preview}。"
                "迁移已回滚。"
            )

        connection.commit()

    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise

    finally:
        connection.execute(
            (
                "PRAGMA foreign_keys = ON"
                if original_foreign_keys
                else
                "PRAGMA foreign_keys = OFF"
            )
        )

    restored_foreign_keys = int(
        connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]
    )

    if (
        restored_foreign_keys
        != original_foreign_keys
    ):
        raise RuntimeError(
            "canal_units schema 迁移完成后"
            "未能恢复 SQLite foreign_keys 状态。"
        )

    return {
        "rebuilt": True,
        "legacy_assignment_count": (
            legacy_assignment_count
        ),
        "row_count": row_count_before,
    }


def _ensure_v102_engineering_code_scope_schema(
    connection,
):
    """
    V1.0.2 编号模型迁移。

    旧模型：UNIQUE(project_id, business_code)

    新模型：
    - business_code 不再承担工程身份；
    - 不同具体渠道允许相同五段式编号；
    - provisional 编号允许临时重复；
    - final 编号仅在具体渠道内唯一。
    """
    row = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'engineering_assets'
        """
    ).fetchone()

    if row is None:
        return {"rebuilt": False}

    compact_sql = "".join(
        str(row["sql"] or "").lower().split()
    )

    if "unique(project_id,business_code)" not in compact_sql:
        return {"rebuilt": False}

    columns = {
        item["name"]
        for item in connection.execute(
            "PRAGMA table_info(engineering_assets)"
        ).fetchall()
    }

    def source(column_name, fallback_sql):
        return column_name if column_name in columns else fallback_sql

    if connection.in_transaction:
        connection.commit()

    original_foreign_keys = int(
        connection.execute("PRAGMA foreign_keys").fetchone()[0]
    )
    connection.execute("PRAGMA foreign_keys = OFF")

    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "DROP TABLE IF EXISTS engineering_assets__code_scope_v102"
        )
        connection.execute(
            """
            CREATE TABLE engineering_assets__code_scope_v102 (
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
                    CHECK (status IN ('active','inactive','retired')),
                notes TEXT,
                created_at TEXT NOT NULL
                    DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL
                    DEFAULT (datetime('now','localtime')),
                engineering_asset_uid TEXT,
                revision_no INTEGER NOT NULL DEFAULT 1
                    CHECK (revision_no >= 1),
                source_revision_no INTEGER NOT NULL DEFAULT 0
                    CHECK (source_revision_no >= 0),
                code_status TEXT NOT NULL DEFAULT 'final'
                    CHECK (code_status IN ('provisional','final')),
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (organization_unit_id)
                    REFERENCES organization_units(id),
                FOREIGN KEY (canal_unit_id) REFERENCES canal_units(id),
                FOREIGN KEY (first_survey_batch_id)
                    REFERENCES survey_batches(id)
            )
            """
        )

        before_count = int(
            connection.execute(
                "SELECT COUNT(*) AS value FROM engineering_assets"
            ).fetchone()["value"]
        )

        connection.execute(
            f"""
            INSERT INTO engineering_assets__code_scope_v102 (
                id,
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
                first_survey_batch_id,
                status,
                notes,
                created_at,
                updated_at,
                engineering_asset_uid,
                revision_no,
                source_revision_no,
                code_status
            )
            SELECT
                id,
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
                first_survey_batch_id,
                status,
                notes,
                created_at,
                updated_at,
                {source('engineering_asset_uid', 'NULL')},
                {source('revision_no', '1')},
                {source('source_revision_no', '0')},
                {source('code_status', "'final'")}
            FROM engineering_assets
            ORDER BY id
            """
        )

        after_count = int(
            connection.execute(
                "SELECT COUNT(*) AS value "
                "FROM engineering_assets__code_scope_v102"
            ).fetchone()["value"]
        )
        if after_count != before_count:
            raise RuntimeError(
                "engineering_assets 编号作用域迁移复制行数不一致。"
            )

        connection.execute("DROP TABLE engineering_assets")
        connection.execute(
            "ALTER TABLE engineering_assets__code_scope_v102 "
            "RENAME TO engineering_assets"
        )
        connection.commit()

    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise

    finally:
        connection.execute(
            "PRAGMA foreign_keys = ON"
            if original_foreign_keys
            else "PRAGMA foreign_keys = OFF"
        )

    if original_foreign_keys:
        problems = connection.execute("PRAGMA foreign_key_check").fetchall()
        if problems:
            preview = "; ".join(str(tuple(item)) for item in problems[:5])
            raise RuntimeError(
                "engineering_assets 编号作用域迁移后外键检查失败："
                f"{preview}"
            )

    return {"rebuilt": True, "row_count": before_count}


def _ensure_survey_record_provenance_schema(
    connection,
):
    """
    保证 SurveyRecord 任务来源字段属于 database.py 核心 schema。

    新数据库的 CREATE TABLE 已包含这些列；
    对开发阶段已有数据库则在 init_database() 中幂等补齐。
    """
    columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(survey_records)"
        ).fetchall()
    }

    if "source_task_uid" not in columns:
        connection.execute(
            """
            ALTER TABLE survey_records
            ADD COLUMN source_task_uid TEXT
            """
        )

    if "source_management_scope_uid" not in columns:
        connection.execute(
            """
            ALTER TABLE survey_records
            ADD COLUMN source_management_scope_uid TEXT
            """
        )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_survey_records_source_task_uid
        ON survey_records(
            source_task_uid,
            id
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_survey_records_source_scope_uid
        ON survey_records(
            source_task_uid,
            source_management_scope_uid,
            id
        )
        """
    )

_SURVEY_RECORD_SIGNATURE_COLUMNS = (
    "surveyor_signatures",
    "water_office_manager_signature",
    "engineering_section_chief_signature",
    "department_head_signature",
)


def _ensure_survey_record_signature_schema(
    connection,
):
    # V1.0.1: 附表2公共签字字段。
    # 调查人可能不止一人，surveyor_signatures 保存原样多人文本。
    columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(survey_records)"
        ).fetchall()
    }

    for column_name in _SURVEY_RECORD_SIGNATURE_COLUMNS:
        if column_name in columns:
            continue

        connection.execute(
            "ALTER TABLE survey_records "
            f"ADD COLUMN {column_name} TEXT"
        )



def _ensure_v102_production_feedback_schema(
    connection,
):
    """
    V1.0.2 生产反馈基础字段。

    revision_no:
        当前本地实体内容版本，内容修改时递增。

    source_revision_no:
        最近一次从成果包接收的下级版本。
        上级本地修改只递增 revision_no，
        不修改 source_revision_no，
        后续用于识别“仅下级更新 / 上下级双方均修改”。

    code_status:
        工程业务编号状态。
        既有 V1.0.1 数据迁移后视为 final；
        后续新增工程将在编号重构阶段改为 provisional。
    """
    asset_columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(engineering_assets)"
        ).fetchall()
    }

    if "revision_no" not in asset_columns:
        connection.execute(
            """
            ALTER TABLE engineering_assets
            ADD COLUMN revision_no INTEGER
            NOT NULL DEFAULT 1
            CHECK (revision_no >= 1)
            """
        )

    if "source_revision_no" not in asset_columns:
        connection.execute(
            """
            ALTER TABLE engineering_assets
            ADD COLUMN source_revision_no INTEGER
            NOT NULL DEFAULT 0
            CHECK (source_revision_no >= 0)
            """
        )

    if "code_status" not in asset_columns:
        connection.execute(
            """
            ALTER TABLE engineering_assets
            ADD COLUMN code_status TEXT
            NOT NULL DEFAULT 'final'
            CHECK (
                code_status IN (
                    'provisional',
                    'final'
                )
            )
            """
        )

    record_columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(survey_records)"
        ).fetchall()
    }

    if "revision_no" not in record_columns:
        connection.execute(
            """
            ALTER TABLE survey_records
            ADD COLUMN revision_no INTEGER
            NOT NULL DEFAULT 1
            CHECK (revision_no >= 1)
            """
        )

    if "source_revision_no" not in record_columns:
        connection.execute(
            """
            ALTER TABLE survey_records
            ADD COLUMN source_revision_no INTEGER
            NOT NULL DEFAULT 0
            CHECK (source_revision_no >= 0)
            """
        )

    # V1.0.1 以前已经由成果包导入的记录没有来源版本字段。
    # 升级时把其当前内容视为“已接收 revision 1”基线。
    connection.execute(
        """
        UPDATE survey_records
        SET source_revision_no = revision_no
        WHERE source_revision_no = 0
          AND source_task_uid IS NOT NULL
          AND trim(source_task_uid) <> ''
        """
    )

    # 与既有下级成果记录关联的工程对象同样建立来源版本基线。
    # 某些历史数据库的 survey_records 只有极简旧字段；
    # engineering_asset_id 尚不存在时必须跳过关联回填，
    # 不能让 V1.0.2 新迁移阻断更早版本的安全升级路径。
    if "engineering_asset_id" in record_columns:
        connection.execute(
            """
            UPDATE engineering_assets
            SET source_revision_no = revision_no
            WHERE source_revision_no = 0
              AND EXISTS (
                  SELECT 1
                  FROM survey_records AS sr
                  WHERE sr.engineering_asset_id
                        = engineering_assets.id
                    AND sr.source_task_uid IS NOT NULL
                    AND trim(sr.source_task_uid) <> ''
              )
            """
        )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_engineering_assets_code_status
        ON engineering_assets (
            project_id,
            canal_unit_id,
            code_status,
            id
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_survey_records_revision
        ON survey_records (
            survey_record_uid,
            revision_no,
            source_revision_no
        )
        """
    )

    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
            uq_engineering_assets_final_business_code_scope
        ON engineering_assets (
            project_id,
            canal_unit_id,
            business_code
        )
        WHERE code_status = 'final'
        """
    )


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
                    REFERENCES canal_units(id)
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

                source_task_uid TEXT,
                source_management_scope_uid TEXT,

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

                surveyor_signatures TEXT,
                water_office_manager_signature TEXT,
                engineering_section_chief_signature TEXT,
                department_head_signature TEXT,

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

            CREATE TABLE IF NOT EXISTS survey_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                media_uid TEXT NOT NULL UNIQUE,

                survey_record_id INTEGER NOT NULL,

                media_kind TEXT NOT NULL
                    CHECK (
                        media_kind IN (
                            'photo',
                            'video'
                        )
                    ),

                media_role TEXT NOT NULL DEFAULT 'other'
                    CHECK (
                        media_role IN (
                            'overview',
                            'location',
                            'detail',
                            'problem',
                            'other'
                        )
                    ),

                item_code TEXT,
                part_name TEXT,

                sequence_no INTEGER NOT NULL DEFAULT 1
                    CHECK (sequence_no > 0),

                original_filename TEXT NOT NULL,
                stored_relative_path TEXT NOT NULL UNIQUE,

                file_sha256 TEXT NOT NULL,
                file_size INTEGER NOT NULL
                    CHECK (file_size >= 0),

                captured_at TEXT,
                notes TEXT,

                created_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                updated_at TEXT NOT NULL
                    DEFAULT (datetime('now', 'localtime')),

                UNIQUE (
                    survey_record_id,
                    file_sha256
                ),

                FOREIGN KEY (survey_record_id)
                    REFERENCES survey_records(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
                idx_survey_media_record
            ON survey_media (
                survey_record_id,
                sequence_no,
                id
            );

            """)

        _ensure_canal_unit_physical_schema(
            connection
        )

        _ensure_v102_engineering_code_scope_schema(
            connection
        )

        _ensure_survey_record_provenance_schema(
            connection
        )

        _ensure_survey_record_signature_schema(
            connection
        )

        _ensure_stable_identity_schema(connection)

        _ensure_v102_production_feedback_schema(
            connection
        )

        _ensure_official_master_data_schema(connection)


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
    初始化系统内置工程调查表定义。

    已接入的附表2工程调查表统一由
    Engineering Form Framework 管理。

    数据库初始化元数据统一从
    EngineeringFormRegistry 中的正式
    EngineeringFormDefinition 生成，
    工程表单元数据统一由 EngineeringFormRegistry 提供。
    """

    # 使用函数内导入，
    # 避免 database 模块加载阶段
    # 对 forms 层形成顶层循环依赖。
    from forms.engineering.registry import (
        get_engineering_form_definitions,
    )

    registered_definitions = (
        get_engineering_form_definitions()
    )

    forms = []

    for definition in registered_definitions:
        form_number_parts = (
            definition.form_number.split(
                ".",
                1,
            )
        )

        if (
            len(form_number_parts) != 2
            or form_number_parts[0] != "2"
            or not (
                form_number_parts[1]
                .isdigit()
            )
        ):
            raise ValueError(
                "无法根据工程调查表编号生成 "
                "数据库排序值："
                f"{definition.form_number}"
            )

        sort_order = (
            200
            + int(
                form_number_parts[1]
            )
        )

        forms.append(
            {
                "form_code": (
                    definition.form_code
                ),
                "form_number": (
                    definition.form_number
                ),
                "form_name": (
                    definition.form_name
                ),
                "series": "series_2",
                "record_type": (
                    "engineering"
                ),
                "asset_type": (
                    definition.asset_type
                ),
                "sort_order": (
                    sort_order
                ),
            }
        )

    with get_connection() as connection:
        for form in forms:
            existing = connection.execute(
                """
                SELECT id
                FROM form_definitions
                WHERE form_code = ?
                """,
                (
                    form["form_code"],
                ),
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
                        form[
                            "form_code"
                        ],
                        form[
                            "form_number"
                        ],
                        form[
                            "form_name"
                        ],
                        form[
                            "series"
                        ],
                        form[
                            "record_type"
                        ],
                        form[
                            "asset_type"
                        ],
                        form[
                            "sort_order"
                        ],
                    ),
                )

                form_definition_id = (
                    cursor.lastrowid
                )

            else:
                form_definition_id = (
                    existing["id"]
                )

            version = connection.execute(
                """
                SELECT id
                FROM form_versions
                WHERE form_definition_id = ?
                AND version_code = 'V1'
                """,
                (
                    form_definition_id,
                ),
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

    渠道管理关系只读取 CanalManagementScope。
    CanalUnit 不再保存组织管理归属。
    基层处的业务引用同时包括直属末级管理单位产生的
    工程和调查记录。
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
            raise ValueError(
                "没有找到指定组织机构。"
            )

        child_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM organization_units
            WHERE parent_id = ?
            """,
            (unit_id,),
        ).fetchone()[0]

        scope_table_exists = (
            connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'canal_management_scopes'
                """
            ).fetchone()
            is not None
        )

        management_scope_count = 0

        if scope_table_exists:
            management_scope_count = (
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM canal_management_scopes
                    WHERE organization_unit_id = ?
                    """,
                    (unit_id,),
                ).fetchone()[0]
            )

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
            descendant_asset_count = (
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM engineering_assets AS ea
                    JOIN organization_units AS ou
                      ON ea.organization_unit_id = ou.id
                    WHERE ou.parent_id = ?
                    """,
                    (unit_id,),
                ).fetchone()[0]
            )

            descendant_survey_count = (
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM survey_records AS sr
                    JOIN organization_units AS ou
                      ON sr.organization_unit_id = ou.id
                    WHERE ou.parent_id = ?
                    """,
                    (unit_id,),
                ).fetchone()[0]
            )

        business_reference_count = (
            asset_count
            + survey_count
            + descendant_asset_count
            + descendant_survey_count
        )

        return {
            "child_count": int(
                child_count
            ),
            "management_scope_count": int(
                management_scope_count
            ),
            "asset_count": int(
                asset_count
            ),
            "survey_count": int(
                survey_count
            ),
            "descendant_asset_count": int(
                descendant_asset_count
            ),
            "descendant_survey_count": int(
                descendant_survey_count
            ),
            "business_reference_count": int(
                business_reference_count
            ),
            "business_code_locked": (
                business_reference_count > 0
            ),
            "can_delete": (
                child_count == 0
                and management_scope_count == 0
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

    已存在下属机构、渠道管理范围、
    工程台账或调查记录时禁止删除。
    """

    usage = get_organization_unit_usage(
        unit_id
    )

    if not usage["can_delete"]:
        reasons = []

        if usage["child_count"]:
            reasons.append(
                f"下属机构 {usage['child_count']} 个"
            )

        if usage[
            "management_scope_count"
        ]:
            reasons.append(
                "渠道管理范围 "
                f"{usage['management_scope_count']} 条"
            )

        if usage["asset_count"]:
            reasons.append(
                f"工程对象 {usage['asset_count']} 个"
            )

        if usage["survey_count"]:
            reasons.append(
                f"调查记录 {usage['survey_count']} 条"
            )

        reason_text = "、".join(
            reasons
        )

        raise ValueError(
            "该组织机构不能物理删除，"
            f"当前存在：{reason_text}。"
            "请改为停用。"
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
    获取全部物理渠系。

    渠道管理单位不再从 canal_units 读取；
    管理关系统一由 CanalManagementScope 提供。
    """

    with get_connection() as connection:
        return connection.execute(
            """
            SELECT *
            FROM canal_units
            ORDER BY id
            """
        ).fetchall()


def create_canal_unit(
    name,
    canal_level,
    parent_id=None,
    description=None,
):
    """
    新增物理渠系。

    CanalUnit 只描述渠道实体和层级；
    管理单位/分管范围必须通过 CanalManagementScope 维护。
    """

    if not name or not name.strip():
        raise ValueError(
            "渠道名称不能为空。"
        )

    if canal_level not in (
        "01",
        "02",
        "03",
        "04",
    ):
        raise ValueError(
            "无效的渠道层级。"
        )

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO canal_units (
                parent_id,
                name,
                canal_level,
                description
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                parent_id,
                name.strip(),
                canal_level,
                (
                    description.strip()
                    if description
                    else None
                ),
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

        scope_table_exists = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'canal_management_scopes'
            """
        ).fetchone() is not None

        management_scope_count = 0

        if scope_table_exists:
            management_scope_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM canal_management_scopes
                WHERE canal_unit_id = ?
                """,
                (canal_unit_id,),
            ).fetchone()[0]

        business_reference_count = asset_count + survey_count

        return {
            "child_count": int(child_count),
            "asset_count": int(asset_count),
            "survey_count": int(survey_count),
            "management_scope_count": int(management_scope_count),
            "business_reference_count": int(business_reference_count),
            "structure_locked": (business_reference_count > 0),
            "can_delete": (
                child_count == 0
                and management_scope_count == 0
                and asset_count == 0
                and survey_count == 0
            ),
        }


def update_canal_unit(
    canal_unit_id,
    name,
    canal_level,
    parent_id=None,
    description=None,
):
    """
    修改物理渠系。

    已产生工程/调查数据后：
    - 名称、备注允许修改；
    - 渠道层级、上级渠道锁定。

    管理单位/分管范围不属于 CanalUnit 编辑职责，
    统一由 CanalManagementScope 维护。
    """

    name = str(
        name or ""
    ).strip()

    description = (
        str(description).strip()
        if description is not None
        else ""
    )

    if not name:
        raise ValueError(
            "渠道名称不能为空。"
        )

    if canal_level not in (
        "01",
        "02",
        "03",
        "04",
    ):
        raise ValueError(
            "无效的渠道层级。"
        )

    current = get_canal_unit(
        canal_unit_id
    )

    if current is None:
        raise ValueError(
            "没有找到指定渠系。"
        )

    if parent_id == canal_unit_id:
        raise ValueError(
            "渠道不能把自己设为上级渠道。"
        )

    usage = get_canal_unit_usage(
        canal_unit_id
    )

    structure_changed = (
        canal_level
        != current["canal_level"]
        or parent_id
        != current["parent_id"]
    )

    if (
        structure_changed
        and usage["structure_locked"]
    ):
        raise ValueError(
            "该渠系已经产生工程或调查数据，"
            "渠道层级和上级渠道不能再修改。"
        )

    with get_connection() as connection:
        current_parent_id = parent_id
        visited_ids = set()

        while (
            current_parent_id
            is not None
        ):
            if (
                current_parent_id
                == canal_unit_id
            ):
                raise ValueError(
                    "渠系层级不能形成循环引用。"
                )

            if (
                current_parent_id
                in visited_ids
            ):
                raise ValueError(
                    "渠系层级存在循环引用。"
                )

            visited_ids.add(
                current_parent_id
            )

            parent = connection.execute(
                """
                SELECT
                    id,
                    parent_id
                FROM canal_units
                WHERE id = ?
                """,
                (
                    current_parent_id,
                ),
            ).fetchone()

            if parent is None:
                raise ValueError(
                    "上级渠道不存在。"
                )

            current_parent_id = (
                parent["parent_id"]
            )

        connection.execute(
            """
            UPDATE canal_units
            SET
                parent_id = ?,
                name = ?,
                canal_level = ?,
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

        if usage["management_scope_count"]:
            reasons.append(
                f"渠道管理范围 {usage['management_scope_count']} 条"
            )

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


def get_engineering_business_codes(
    project_id,
    canal_unit_id=None,
):
    """
    获取工程业务编号。

    正式调查页面传入具体 canal_unit_id，
    使不同物理渠道各自从 001 开始暂编。
    canal_unit_id 为空时保留旧调用语义。
    """
    with get_connection() as connection:
        if canal_unit_id is None:
            rows = connection.execute(
                """
                SELECT business_code
                FROM engineering_assets
                WHERE project_id = ?
                ORDER BY id
                """,
                (project_id,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT business_code
                FROM engineering_assets
                WHERE project_id = ?
                  AND canal_unit_id = ?
                ORDER BY id
                """,
                (project_id, canal_unit_id),
            ).fetchall()

        return [
            row["business_code"]
            for row in rows
            if row["business_code"]
        ]


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

    供：
    - 数据查询；
    - 附表2工程当前批次公共列表页
      共同使用。

    在所有工程公共字段之外，
    同时返回：
    - point / range 原始桩号文本；
    - record_data。

    这样不同附表的列表页无需再建立
    各自的专属查询函数。
    """

    if project_id is None:
        return []

    sql = """
        SELECT
            sr.id AS survey_record_id,
            sr.project_id,
            sr.survey_batch_id,
            sr.organization_unit_id,
            sr.canal_unit_id,

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
            sr.record_data_json,
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

        parameters.append(
            survey_batch_id
        )

    if form_code:
        sql += """
          AND fd.form_code = ?
        """

        parameters.append(
            form_code
        )

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
        single_stake = (
            row["single_stake_text"]
            or ""
        )

        start_stake = (
            row["start_stake_text"]
            or ""
        )

        end_stake = (
            row["end_stake_text"]
            or ""
        )

        try:
            record_data = json.loads(
                row[
                    "record_data_json"
                ]
                or "{}"
            )

        except json.JSONDecodeError:
            record_data = {}

        # =====================================================
        # 统一工程位置
        # =====================================================

        if (
            start_stake
            and end_stake
        ):
            engineering_position = (
                f"{start_stake} ～ "
                f"{end_stake}"
            )

        elif start_stake:
            engineering_position = (
                start_stake
            )

        elif end_stake:
            engineering_position = (
                end_stake
            )

        else:
            engineering_position = (
                single_stake
            )

        form_display_name = (
            f"附表"
            f"{row['form_number']} "
            f"{row['form_name']}"
        )

        result.append(
            {
                "survey_record_id": (
                    row[
                        "survey_record_id"
                    ]
                ),
                "engineering_asset_id": (
                    row[
                        "engineering_asset_id"
                    ]
                ),
                "project_id": (
                    row["project_id"]
                ),
                "survey_batch_id": (
                    row[
                        "survey_batch_id"
                    ]
                ),
                "organization_unit_id": (
                    row[
                        "organization_unit_id"
                    ]
                ),
                "canal_unit_id": (
                    row[
                        "canal_unit_id"
                    ]
                ),
                "batch_name": (
                    row["batch_name"]
                    or ""
                ),
                "batch_code": (
                    row["batch_code"]
                    or ""
                ),
                "form_code": (
                    row["form_code"]
                ),
                "form_number": (
                    row["form_number"]
                ),
                "form_name": (
                    row["form_name"]
                ),
                "form_display_name": (
                    form_display_name
                ),
                "asset_type": (
                    row["asset_type"]
                ),
                "business_code": (
                    row["business_code"]
                    or ""
                ),
                "asset_name": (
                    row["asset_name"]
                    or ""
                ),
                "department_name": (
                    row["department_name"]
                    or ""
                ),
                "office_name": (
                    row["office_name"]
                    or ""
                ),
                "canal_name": (
                    row["canal_name"]
                    or ""
                ),

                # ---------------------------------------------
                # 原始位置
                # ---------------------------------------------
                "single_stake_text": (
                    single_stake
                ),
                "start_stake_text": (
                    start_stake
                ),
                "end_stake_text": (
                    end_stake
                ),

                # ---------------------------------------------
                # 统一位置
                # ---------------------------------------------
                "engineering_position": (
                    engineering_position
                ),

                # ---------------------------------------------
                # 表单业务数据
                # ---------------------------------------------
                "record_data": (
                    record_data
                ),

                "overall_grade": (
                    row["overall_grade"]
                ),
                "survey_date": (
                    row["survey_date"]
                    or ""
                ),
                "record_status": (
                    row["record_status"]
                ),
                "updated_at": (
                    row["updated_at"]
                    or ""
                ),
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
    surveyor_signatures=None,
    water_office_manager_signature=None,
    engineering_section_chief_signature=None,
    department_head_signature=None,
    source_management_scope_uid=None,
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

        engineering_asset_id = (
            asset_cursor.lastrowid
        )

        connection.execute(
            """
            UPDATE engineering_assets
            SET code_status = 'provisional'
            WHERE id = ?
            """,
            (engineering_asset_id,),
        )

        record_cursor = connection.execute(
            """
            INSERT INTO survey_records (
                project_id,
                survey_batch_id,
                form_version_id,
                record_type,
                organization_unit_id,
                canal_unit_id,
                source_management_scope_uid,
                engineering_asset_id,
                business_code,
                survey_date,
                overall_grade,
                survey_comment,
                surveyor_signatures,
                water_office_manager_signature,
                engineering_section_chief_signature,
                department_head_signature,
                record_status,
                record_data_json
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                project_id,
                survey_batch_id,
                form_version_id,
                "engineering",
                organization_unit_id,
                canal_unit_id,
                source_management_scope_uid,
                engineering_asset_id,
                business_code,
                survey_date,
                overall_grade,
                survey_comment,
                surveyor_signatures,
                water_office_manager_signature,
                engineering_section_chief_signature,
                department_head_signature,
                "draft",
                record_json,
            ),
        )

        survey_record_id = (
            record_cursor.lastrowid
        )

        if inspection_results is not None:
            _replace_inspection_results(
                connection,
                survey_record_id,
                inspection_results,
            )

        return {
            "engineering_asset_id": (
                engineering_asset_id
            ),
            "survey_record_id": (
                survey_record_id
            ),
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
    surveyor_signatures=None,
    water_office_manager_signature=None,
    engineering_section_chief_signature=None,
    department_head_signature=None,
    source_management_scope_uid=None,
):
    """
    第一次保存区间型工程调查时，
    同时创建 EngineeringAsset 和 SurveyRecord。
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
        duplicate = (
            _find_duplicate_range_engineering_survey(
                connection=connection,
                project_id=project_id,
                survey_batch_id=survey_batch_id,
                form_version_id=form_version_id,
                organization_unit_id=(
                    organization_unit_id
                ),
                canal_unit_id=canal_unit_id,
                start_stake_value=(
                    start_stake_value
                ),
                end_stake_value=(
                    end_stake_value
                ),
            )
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

        engineering_asset_id = (
            asset_cursor.lastrowid
        )

        connection.execute(
            """
            UPDATE engineering_assets
            SET code_status = 'provisional'
            WHERE id = ?
            """,
            (engineering_asset_id,),
        )

        record_cursor = connection.execute(
            """
            INSERT INTO survey_records (
                project_id,
                survey_batch_id,
                form_version_id,
                record_type,
                organization_unit_id,
                canal_unit_id,
                source_management_scope_uid,
                engineering_asset_id,
                business_code,
                survey_date,
                overall_grade,
                survey_comment,
                surveyor_signatures,
                water_office_manager_signature,
                engineering_section_chief_signature,
                department_head_signature,
                record_status,
                record_data_json
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                project_id,
                survey_batch_id,
                form_version_id,
                "engineering",
                organization_unit_id,
                canal_unit_id,
                source_management_scope_uid,
                engineering_asset_id,
                business_code,
                survey_date,
                overall_grade,
                survey_comment,
                surveyor_signatures,
                water_office_manager_signature,
                engineering_section_chief_signature,
                department_head_signature,
                "draft",
                record_json,
            ),
        )

        survey_record_id = (
            record_cursor.lastrowid
        )

        if inspection_results is not None:
            _replace_inspection_results(
                connection,
                survey_record_id,
                inspection_results,
            )

        return {
            "engineering_asset_id": (
                engineering_asset_id
            ),
            "survey_record_id": (
                survey_record_id
            ),
            "business_code": business_code,
        }


def complete_engineering_survey_record(
    survey_record_id,
    form_code,
    position_kind,
    expected_item_codes,
    grade_options,
):
    """
    通用工程调查完成事务。

    本函数只负责已经保存到数据库中的
    公共业务完整性和状态转换。

    表单专属字段完整性由
    forms.engineering.validation
    基于 EngineeringFormDefinition
    在进入本函数前完成。

    当前检查：
    - 记录存在且属于指定表单；
    - 当前状态必须为 draft；
    - 工程公共身份完整；
    - point / range 位置完整；
    - 调查日期有效；
    - 工程状况类别有效；
    - 调查意见存在；
    - definition 声明的评价项全部存在；
    - 评价等级属于允许等级；
    - 最后原子更新为 completed。
    """

    form_code = str(form_code or "").strip()

    position_kind = str(position_kind or "").strip()

    expected_item_codes = tuple(
        str(code).strip() for code in (expected_item_codes or ()) if str(code).strip()
    )

    grade_options = tuple(
        str(grade).strip() for grade in (grade_options or ()) if str(grade).strip()
    )

    if not form_code:
        raise ValueError("调查表代码不能为空。")

    if position_kind not in (
        "point",
        "range",
    ):
        raise ValueError("不支持的工程位置类型：" f"{position_kind}")

    if not expected_item_codes:
        raise ValueError("当前调查表没有配置" "有效的评价项目。")

    if len(set(expected_item_codes)) != len(expected_item_codes):
        raise ValueError("当前调查表评价项目代码" "存在重复。")

    if not grade_options:
        raise ValueError("当前调查表没有配置" "有效的评价等级。")

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

                ea.asset_name,

                ea.single_stake_text,
                ea.single_stake_value,

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
              AND fd.form_code = ?
            """,
            (
                survey_record_id,
                form_code,
            ),
        ).fetchone()

        if record is None:
            raise ValueError("没有找到该调查记录，" "或调查表类型不匹配。")

        if record["record_status"] != "draft":
            raise ValueError("只有草稿记录可以" "执行完成调查。")

        # =====================================================
        # 公共工程身份
        # =====================================================

        missing_fields = []

        asset_name = str(record["asset_name"] or "").strip()

        business_code = str(record["business_code"] or "").strip()

        survey_date = str(record["survey_date"] or "").strip()

        survey_comment = str(record["survey_comment"] or "").strip()

        if not asset_name:
            missing_fields.append("工程名称")

        if record["organization_unit_id"] is None:
            missing_fields.append("所属水管所")

        if record["canal_unit_id"] is None:
            missing_fields.append("所属渠系")

        if not business_code:
            missing_fields.append("业务编号")

        # =====================================================
        # 工程位置
        # =====================================================

        if position_kind == "point":
            if not str(record["single_stake_text"] or "").strip():
                missing_fields.append("工程桩号")

            if record["single_stake_value"] is None:
                missing_fields.append("工程桩号数值")

        else:
            if not str(record["start_stake_text"] or "").strip():
                missing_fields.append("起始桩号")

            if record["start_stake_value"] is None:
                missing_fields.append("起始桩号数值")

            if not str(record["end_stake_text"] or "").strip():
                missing_fields.append("终止桩号")

            if record["end_stake_value"] is None:
                missing_fields.append("终止桩号数值")

            start_value = record["start_stake_value"]

            end_value = record["end_stake_value"]

            if (
                start_value is not None
                and end_value is not None
                and end_value < start_value
            ):
                raise ValueError("终止桩号不能小于" "起始桩号。")

        # =====================================================
        # 调查结论
        # =====================================================

        if not survey_date:
            missing_fields.append("调查时间")

        if record["overall_grade"] not in grade_options:
            missing_fields.append("工程状况类别")

        if not survey_comment:
            missing_fields.append("调查意见与建议")

        if missing_fields:
            field_text = "、".join(missing_fields)

            raise ValueError("完成调查前仍有公共" "必填内容未填写：" f"{field_text}。")

        try:
            datetime.strptime(
                survey_date,
                "%Y-%m-%d",
            )

        except ValueError as error:
            raise ValueError("调查时间不是有效的 " "YYYY-MM-DD 日期。") from error

        # =====================================================
        # 分项评价
        # =====================================================

        result_rows = connection.execute(
            """
            SELECT
                item_code,
                grade
            FROM inspection_results
            WHERE survey_record_id = ?
            """,
            (survey_record_id,),
        ).fetchall()

        result_map = {row["item_code"]: row["grade"] for row in result_rows}

        missing_item_codes = [
            item_code
            for item_code in expected_item_codes
            if item_code not in result_map
        ]

        if missing_item_codes:
            raise ValueError(
                "完成调查前必须完成"
                "全部分项评价。"
                f"当前还缺 "
                f"{len(missing_item_codes)} 项。"
            )

        invalid_item_codes = [
            item_code
            for item_code in expected_item_codes
            if result_map.get(item_code) not in grade_options
        ]

        if invalid_item_codes:
            raise ValueError("存在无效的分项评价等级。")

        # =====================================================
        # 正式完成
        # =====================================================

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
            "inspection_count": len(expected_item_codes),
        }


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


def get_point_engineering_record(
    survey_record_id,
    form_code,
):
    """
    获取一条点状工程调查记录。
    """

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                sr.id AS survey_record_id,
                sr.record_status,
                sr.source_task_uid,
                sr.source_management_scope_uid,
                sr.business_code,
                sr.record_data_json,
                sr.survey_date,
                sr.overall_grade,
                sr.survey_comment,
                sr.surveyor_signatures,
                sr.water_office_manager_signature,
                sr.engineering_section_chief_signature,
                sr.department_head_signature,

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
            record_data = json.loads(
                row["record_data_json"]
                or "{}"
            )
        except json.JSONDecodeError:
            record_data = {}

        return {
            "survey_record_id": (
                row["survey_record_id"]
            ),
            "engineering_asset_id": (
                row["engineering_asset_id"]
            ),
            "record_status": (
                row["record_status"]
            ),
            "source_task_uid": (
                row["source_task_uid"]
            ),
            "source_management_scope_uid": (
                row[
                    "source_management_scope_uid"
                ]
            ),
            "business_code": (
                row["business_code"]
                or ""
            ),
            "asset_name": (
                row["asset_name"]
                or ""
            ),
            "asset_type": row["asset_type"],
            "form_code": row["form_code"],
            "single_stake_text": (
                row["single_stake_text"]
            ),
            "single_stake_value": (
                row["single_stake_value"]
            ),
            "department_id": (
                row["department_id"]
            ),
            "office_id": row["office_id"],
            "canal_id": row["canal_id"],
            "record_data": record_data,
            "survey_date": row["survey_date"],
            "overall_grade": (
                row["overall_grade"]
            ),
            "survey_comment": (
                row["survey_comment"]
                or ""
            ),
            "surveyor_signatures": (
                row["surveyor_signatures"] or ""
            ),
            "water_office_manager_signature": (
                row["water_office_manager_signature"] or ""
            ),
            "engineering_section_chief_signature": (
                row["engineering_section_chief_signature"] or ""
            ),
            "department_head_signature": (
                row["department_head_signature"] or ""
            ),
        }


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
    surveyor_signatures=None,
    water_office_manager_signature=None,
    engineering_section_chief_signature=None,
    department_head_signature=None,
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

        current_asset = connection.execute(
            """
            SELECT single_stake_value, code_status
            FROM engineering_assets
            WHERE id = ?
            """,
            (engineering_asset_id,),
        ).fetchone()

        point_position_changed = (
            current_asset is None
            or current_asset["single_stake_value"] != single_stake_value
        )
        next_code_status = (
            "provisional"
            if point_position_changed
            else (current_asset["code_status"] or "provisional")
        )

        connection.execute(
            """
            UPDATE engineering_assets
            SET
                asset_name = ?,
                code_status = ?,
                single_stake_text = ?,
                single_stake_value = ?,
                revision_no = revision_no + 1,
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (
                asset_name.strip(),
                next_code_status,
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
                surveyor_signatures = ?,
                water_office_manager_signature = ?,
                engineering_section_chief_signature = ?,
                department_head_signature = ?,
                record_data_json = ?,
                revision_no = revision_no + 1,
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
                surveyor_signatures,
                water_office_manager_signature,
                engineering_section_chief_signature,
                department_head_signature,
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
    """

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                sr.id
                    AS survey_record_id,

                sr.project_id,
                sr.survey_batch_id,
                sr.form_version_id,

                sr.organization_unit_id,
                sr.canal_unit_id,

                sr.record_status,
                sr.source_task_uid,
                sr.source_management_scope_uid,
                sr.business_code,
                sr.record_data_json,
                sr.survey_date,
                sr.overall_grade,
                sr.survey_comment,
                sr.surveyor_signatures,
                sr.water_office_manager_signature,
                sr.engineering_section_chief_signature,
                sr.department_head_signature,

                ea.id
                    AS engineering_asset_id,

                ea.asset_name,
                ea.asset_type,

                ea.single_stake_text,
                ea.single_stake_value,

                ea.start_stake_text,
                ea.start_stake_value,
                ea.end_stake_text,
                ea.end_stake_value,

                office.id
                    AS office_id,

                department.id
                    AS department_id,

                canal.id
                    AS canal_id,

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
              AND sr.record_status != 'void'
            """,
            (
                survey_record_id,
                form_code,
            ),
        ).fetchone()

    if row is None:
        return None

    try:
        record_data = json.loads(
            row["record_data_json"]
            or "{}"
        )
    except json.JSONDecodeError:
        record_data = {}

    return {
        "survey_record_id": (
            row["survey_record_id"]
        ),
        "engineering_asset_id": (
            row["engineering_asset_id"]
        ),
        "project_id": row["project_id"],
        "survey_batch_id": (
            row["survey_batch_id"]
        ),
        "form_version_id": (
            row["form_version_id"]
        ),
        "organization_unit_id": (
            row["organization_unit_id"]
        ),
        "canal_unit_id": (
            row["canal_unit_id"]
        ),
        "record_status": (
            row["record_status"]
        ),
        "source_task_uid": (
            row["source_task_uid"]
        ),
        "source_management_scope_uid": (
            row[
                "source_management_scope_uid"
            ]
        ),
        "business_code": (
            row["business_code"]
            or ""
        ),
        "asset_name": (
            row["asset_name"]
            or ""
        ),
        "asset_type": row["asset_type"],
        "form_code": row["form_code"],
        "single_stake_text": (
            row["single_stake_text"]
        ),
        "single_stake_value": (
            row["single_stake_value"]
        ),
        "start_stake_text": (
            row["start_stake_text"]
            or ""
        ),
        "start_stake_value": (
            row["start_stake_value"]
        ),
        "end_stake_text": (
            row["end_stake_text"]
            or ""
        ),
        "end_stake_value": (
            row["end_stake_value"]
        ),
        "department_id": (
            row["department_id"]
        ),
        "office_id": row["office_id"],
        "canal_id": row["canal_id"],
        "record_data": record_data,
        "survey_date": row["survey_date"],
        "overall_grade": (
            row["overall_grade"]
        ),
        "survey_comment": (
            row["survey_comment"]
            or ""
        ),
        "surveyor_signatures": (
            row["surveyor_signatures"] or ""
        ),
        "water_office_manager_signature": (
            row["water_office_manager_signature"] or ""
        ),
        "engineering_section_chief_signature": (
            row["engineering_section_chief_signature"] or ""
        ),
        "department_head_signature": (
            row["department_head_signature"] or ""
        ),
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
    surveyor_signatures=None,
    water_office_manager_signature=None,
    engineering_section_chief_signature=None,
    department_head_signature=None,
    organization_unit_id=None,
    canal_unit_id=None,
    business_code=None,
):
    """
    修改已有区间型工程调查记录。

    支持 draft / completed。

    organization_unit_id、
    canal_unit_id、business_code
    未传入时保持原值，
    因此现有2.5调用无需修改。

    附表2.1等需要修改工程归属时，
    可以显式传入新的值。
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
                sr.business_code,

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

        # =====================================================
        # 目标归属信息
        # =====================================================

        target_organization_unit_id = (
            record["organization_unit_id"]
            if organization_unit_id is None
            else organization_unit_id
        )

        target_canal_unit_id = (
            record["canal_unit_id"] if canal_unit_id is None else canal_unit_id
        )

        target_business_code = (
            record["business_code"]
            if business_code is None
            else str(business_code).strip()
        )

        if target_organization_unit_id is None:
            raise ValueError("所属水管所不能为空。")

        if target_canal_unit_id is None:
            raise ValueError("所属渠系不能为空。")

        if not target_business_code:
            raise ValueError("业务编号不能为空。")

        # =====================================================
        # 区间重复保护
        # =====================================================

        duplicate = _find_duplicate_range_engineering_survey(
            connection=connection,
            project_id=(record["project_id"]),
            survey_batch_id=(record["survey_batch_id"]),
            form_version_id=(record["form_version_id"]),
            organization_unit_id=(target_organization_unit_id),
            canal_unit_id=(target_canal_unit_id),
            start_stake_value=(start_stake_value),
            end_stake_value=(end_stake_value),
            exclude_survey_record_id=(survey_record_id),
        )

        if duplicate is not None:
            raise ValueError("当前调查批次中已存在" "相同起止桩号的" "工程调查记录。")

        engineering_asset_id = record["engineering_asset_id"]

        current_asset = connection.execute(
            """
            SELECT start_stake_value, end_stake_value, code_status
            FROM engineering_assets
            WHERE id = ?
            """,
            (engineering_asset_id,),
        ).fetchone()

        range_position_changed = (
            current_asset is None
            or current_asset["start_stake_value"] != start_stake_value
            or current_asset["end_stake_value"] != end_stake_value
        )
        next_code_status = (
            "provisional"
            if range_position_changed
            else (current_asset["code_status"] or "provisional")
        )

        # =====================================================
        # EngineeringAsset
        # =====================================================

        connection.execute(
            """
            UPDATE engineering_assets
            SET
                asset_name = ?,
                code_status = ?,

                organization_unit_id = ?,
                canal_unit_id = ?,
                business_code = ?,

                single_stake_text = NULL,
                single_stake_value = NULL,

                start_stake_text = ?,
                start_stake_value = ?,
                end_stake_text = ?,
                end_stake_value = ?,

                revision_no = revision_no + 1,
                updated_at = datetime(
                    'now',
                    'localtime'
                )

            WHERE id = ?
            """,
            (
                asset_name.strip(),
                next_code_status,
                target_organization_unit_id,
                target_canal_unit_id,
                target_business_code,
                start_stake_text,
                start_stake_value,
                end_stake_text,
                end_stake_value,
                engineering_asset_id,
            ),
        )

        # =====================================================
        # SurveyRecord
        # =====================================================

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
                surveyor_signatures = ?,
                water_office_manager_signature = ?,
                engineering_section_chief_signature = ?,
                department_head_signature = ?,
                record_data_json = ?,

                revision_no = revision_no + 1,
                updated_at = datetime(
                    'now',
                    'localtime'
                )

            WHERE id = ?
            """,
            (
                target_organization_unit_id,
                target_canal_unit_id,
                target_business_code,
                survey_date,
                overall_grade,
                survey_comment,
                surveyor_signatures,
                water_office_manager_signature,
                engineering_section_chief_signature,
                department_head_signature,
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
            "engineering_asset_id": engineering_asset_id,
            "survey_record_id": survey_record_id,
            "business_code": target_business_code,
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
                ea.code_status,
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
                ) AS overall_grade,

                (
                    SELECT sr.id
                    FROM survey_records AS sr
                    WHERE sr.engineering_asset_id = ea.id
                    AND (
                            ? IS NULL
                            OR sr.survey_batch_id = ?
                        )
                    AND sr.record_status != 'void'
                    ORDER BY sr.id DESC
                    LIMIT 1
                ) AS survey_record_id,

                (
                    SELECT fd.form_code
                    FROM survey_records AS sr
                    JOIN form_versions AS fv
                        ON sr.form_version_id = fv.id
                    JOIN form_definitions AS fd
                        ON fv.form_definition_id = fd.id
                    WHERE sr.engineering_asset_id = ea.id
                    AND (
                            ? IS NULL
                            OR sr.survey_batch_id = ?
                        )
                    AND sr.record_status != 'void'
                    ORDER BY sr.id DESC
                    LIMIT 1
                ) AS survey_form_code,

                (
                    SELECT sr.survey_date
                    FROM survey_records AS sr
                    WHERE sr.engineering_asset_id = ea.id
                    AND (
                            ? IS NULL
                            OR sr.survey_batch_id = ?
                        )
                    AND sr.record_status != 'void'
                    ORDER BY sr.id DESC
                    LIMIT 1
                ) AS survey_date

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
                survey_batch_id,
                survey_batch_id,
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

                fd.form_code,
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
