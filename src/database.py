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


def create_initial_forms():
    """
    初始化当前 V0.1 Demo 使用的调查表定义。

    当前先建立：
    - 附表2.1 防渗衬砌渠道
    - 附表2.2 水闸
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
                "水闸调查记录。\n\n"
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


def delete_sluice_gate_record(
    survey_record_id,
):
    """
    删除一条附表2.2水闸调查记录。

    删除规则：
    1. 删除 SurveyRecord；
    2. InspectionResult 通过外键级联自动删除；
    3. 如果对应 EngineeringAsset 已经没有任何调查记录，
       同时删除该工程对象；
    4. 全部操作在同一个 SQLite 事务中完成。
    """

    with get_connection() as connection:

        record = connection.execute(
            """
            SELECT
                sr.id AS survey_record_id,
                sr.engineering_asset_id,
                sr.business_code,
                sr.record_status,

                ea.asset_name

            FROM survey_records AS sr

            JOIN engineering_assets AS ea
                ON sr.engineering_asset_id = ea.id

            JOIN form_versions AS fv
                ON sr.form_version_id = fv.id

            JOIN form_definitions AS fd
                ON fv.form_definition_id = fd.id

            WHERE sr.id = ?
              AND fd.form_code = 'form_2_2'
            """,
            (survey_record_id,),
        ).fetchone()

        if record is None:
            raise ValueError("没有找到需要删除的水闸调查记录。")

        engineering_asset_id = record["engineering_asset_id"]

        # =========================
        # 1. 删除调查记录
        # =========================
        #
        # inspection_results 已配置：
        # ON DELETE CASCADE
        # 因此会自动一起删除。

        connection.execute(
            """
            DELETE FROM survey_records
            WHERE id = ?
            """,
            (survey_record_id,),
        )

        # =========================
        # 2. 检查工程是否仍有其他调查记录
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
        # 3. 删除孤立 EngineeringAsset
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
            "survey_record_id": survey_record_id,
            "engineering_asset_id": engineering_asset_id,
            "business_code": record["business_code"],
            "asset_name": record["asset_name"],
            "record_status": record["record_status"],
            "asset_deleted": asset_deleted,
            "remaining_survey_count": remaining_count,
        }


def get_sluice_gate_record(
    survey_record_id,
):
    """
    获取一条附表2.2水闸调查记录，
    用于重新打开和编辑。
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

                office.id AS office_id,
                department.id AS department_id,

                canal.id AS canal_id

            FROM survey_records AS sr

            JOIN engineering_assets AS ea
                ON sr.engineering_asset_id = ea.id

            LEFT JOIN organization_units AS office
                ON sr.organization_unit_id = office.id

            LEFT JOIN organization_units AS department
                ON office.parent_id = department.id

            LEFT JOIN canal_units AS canal
                ON sr.canal_unit_id = canal.id

            WHERE sr.id = ?
            """,
            (survey_record_id,),
        ).fetchone()

        if row is None:
            return None

        try:
            record_data = json.loads(row["record_data_json"] or "{}")
        except json.JSONDecodeError:
            record_data = {}

        return {
            "survey_record_id": row["survey_record_id"],
            "engineering_asset_id": (row["engineering_asset_id"]),
            "record_status": row["record_status"],
            "business_code": (row["business_code"] or ""),
            "asset_name": row["asset_name"] or "",
            "department_id": row["department_id"],
            "office_id": row["office_id"],
            "canal_id": row["canal_id"],
            "record_data": record_data,
            "survey_date": row["survey_date"],
            "overall_grade": row["overall_grade"],
            "survey_comment": (row["survey_comment"] or ""),
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
    修改已有水闸草稿。

    当前V0.1只修改：
    - 工程名称
    - 桩号
    - 普通调查字段

    不修改：
    - 所属机构
    - 渠系
    - 业务编号
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
                engineering_asset_id,
                record_status,
                project_id,
                survey_batch_id,
                form_version_id,
                organization_unit_id,
                canal_unit_id

            FROM survey_records

            WHERE id = ?
            """,
            (survey_record_id,),
        ).fetchone()

        duplicate = _find_duplicate_engineering_survey(
            connection=connection,
            project_id=record["project_id"],
            survey_batch_id=record["survey_batch_id"],
            form_version_id=record["form_version_id"],
            organization_unit_id=record["organization_unit_id"],
            canal_unit_id=record["canal_unit_id"],
            single_stake_value=single_stake_value,
            exclude_survey_record_id=survey_record_id,
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
                "水闸调查记录。\n\n"
                f"工程名称：{duplicate['asset_name']}\n"
                f"业务编号：{duplicate['business_code']}\n"
                f"桩号：{duplicate['single_stake_text']}\n"
                f"状态：{status_text}\n\n"
                "当前草稿不能修改为该桩号。"
            )

        if record is None:
            raise ValueError("没有找到该调查记录。")

        if record["record_status"] not in (
            "draft",
            "completed",
        ):
            raise ValueError("当前记录状态不允许直接修改。")

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
                ea.start_stake_text,
                ea.end_stake_text,

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
