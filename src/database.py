from pathlib import Path
import sqlite3

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 本地数据目录
DATA_DIR = PROJECT_ROOT / "local_data"

# SQLite 数据库文件
DB_PATH = DATA_DIR / "yinda_survey.db"


def get_connection():
    """
    获取 SQLite 数据库连接。
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
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
            """)


def create_demo_data():
    """
    创建开发测试用的示例项目和调查批次。
    只在数据库为空时创建，不会重复添加。
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
