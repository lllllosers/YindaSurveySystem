from __future__ import annotations

from uuid import uuid4

import database
from services.master_identity import deterministic_master_uid


RANGE_MODE_WHOLE = "whole"
RANGE_MODE_SEGMENT_KNOWN = "segment_known"
RANGE_MODE_SEGMENT_UNKNOWN = "segment_unknown"
VALID_RANGE_MODES = {
    RANGE_MODE_WHOLE,
    RANGE_MODE_SEGMENT_KNOWN,
    RANGE_MODE_SEGMENT_UNKNOWN,
}


def _clean_text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _validate_range(
    range_mode,
    start_stake_text,
    start_stake_value,
    end_stake_text,
    end_stake_value,
):
    if range_mode not in VALID_RANGE_MODES:
        raise ValueError("不支持的渠道管理范围类型。")

    if range_mode in {
        RANGE_MODE_WHOLE,
        RANGE_MODE_SEGMENT_UNKNOWN,
    }:
        if any(
            value is not None
            for value in (
                start_stake_text,
                start_stake_value,
                end_stake_text,
                end_stake_value,
            )
        ):
            raise ValueError(
                "whole / segment_unknown 不能携带起止桩号。"
            )
        return

    if start_stake_value is None or end_stake_value is None:
        raise ValueError(
            "segment_known 必须提供起止桩号数值。"
        )

    if float(start_stake_value) > float(end_stake_value):
        raise ValueError(
            "管理范围起始桩号不能大于终止桩号。"
        )


def _scope_master_key(canal_master_key, organization_master_key):
    return f"CMS-{canal_master_key}-{organization_master_key}"


def _scope_select_sql():
    return """
        SELECT
            cms.id,
            cms.management_scope_uid,
            cms.master_key,
            cms.canal_unit_id,
            canal.canal_unit_uid,
            canal.master_key AS canal_master_key,
            canal.name AS canal_name,
            canal.canal_level,
            canal.sort_order AS canal_sort_order,
            cms.organization_unit_id,
            office.organization_unit_uid,
            office.master_key AS organization_master_key,
            office.name AS organization_name,
            office.business_code AS organization_business_code,
            department.id AS department_id,
            department.name AS department_name,
            department.business_code AS department_business_code,
            cms.range_mode,
            cms.start_stake_text,
            cms.start_stake_value,
            cms.end_stake_text,
            cms.end_stake_value,
            cms.sort_order,
            cms.status,
            cms.description,
            cms.created_at,
            cms.updated_at
        FROM canal_management_scopes AS cms
        JOIN canal_units AS canal
          ON canal.id = cms.canal_unit_id
        JOIN organization_units AS office
          ON office.id = cms.organization_unit_id
        LEFT JOIN organization_units AS department
          ON department.id = office.parent_id
    """


def _create_schema(connection):
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS canal_management_scopes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            management_scope_uid TEXT NOT NULL,
            master_key TEXT,
            canal_unit_id INTEGER NOT NULL,
            organization_unit_id INTEGER NOT NULL,
            range_mode TEXT NOT NULL
                CHECK (
                    range_mode IN (
                        'whole',
                        'segment_known',
                        'segment_unknown'
                    )
                ),
            start_stake_text TEXT,
            start_stake_value REAL,
            end_stake_text TEXT,
            end_stake_value REAL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'inactive')),
            description TEXT,
            created_at TEXT NOT NULL
                DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL
                DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (canal_unit_id)
                REFERENCES canal_units(id),
            FOREIGN KEY (organization_unit_id)
                REFERENCES organization_units(id),
            CHECK (
                (
                    range_mode = 'segment_known'
                    AND start_stake_value IS NOT NULL
                    AND end_stake_value IS NOT NULL
                    AND start_stake_value <= end_stake_value
                )
                OR
                (
                    range_mode IN ('whole', 'segment_unknown')
                    AND start_stake_text IS NULL
                    AND start_stake_value IS NULL
                    AND end_stake_text IS NULL
                    AND end_stake_value IS NULL
                )
            )
        );

        CREATE UNIQUE INDEX IF NOT EXISTS
            uq_canal_management_scopes_uid
        ON canal_management_scopes(management_scope_uid);

        CREATE UNIQUE INDEX IF NOT EXISTS
            uq_canal_management_scopes_master_key
        ON canal_management_scopes(master_key)
        WHERE master_key IS NOT NULL AND trim(master_key) <> '';

        CREATE INDEX IF NOT EXISTS
            idx_canal_management_scopes_canal
        ON canal_management_scopes(
            canal_unit_id,
            status,
            sort_order,
            id
        );

        CREATE INDEX IF NOT EXISTS
            idx_canal_management_scopes_org
        ON canal_management_scopes(
            organization_unit_id,
            status,
            sort_order,
            id
        );

        CREATE TRIGGER IF NOT EXISTS
            trg_canal_management_scopes_uid_immutable
        BEFORE UPDATE OF management_scope_uid
        ON canal_management_scopes
        FOR EACH ROW
        WHEN
            OLD.management_scope_uid IS NOT NULL
            AND trim(OLD.management_scope_uid) <> ''
            AND OLD.management_scope_uid IS NOT NEW.management_scope_uid
        BEGIN
            SELECT RAISE(
                ABORT,
                'management_scope_uid is immutable'
            );
        END;
        """
    )


def ensure_canal_management_scope_schema():
    """
    建立渠道管理范围 schema。

    CanalManagementScope 是渠道管理关系的唯一运行事实源。
    本函数只负责 schema，不再读取或迁移
    canal_units.organization_unit_id。
    """

    with database.get_connection() as connection:
        existed = (
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

        _create_schema(
            connection
        )

        total = int(
            connection.execute(
                """
                SELECT COUNT(*) AS value
                FROM canal_management_scopes
                """
            ).fetchone()["value"]
        )

    return {
        "table_created": not existed,
        "total_scope_count": total,
    }


def create_canal_management_scope(
    *,
    canal_unit_id,
    organization_unit_id,
    range_mode,
    start_stake_text=None,
    start_stake_value=None,
    end_stake_text=None,
    end_stake_value=None,
    sort_order=0,
    status="active",
    description=None,
    master_key=None,
    management_scope_uid=None,
):
    range_mode = str(range_mode or "").strip()
    status = str(status or "").strip()

    if status not in {"active", "inactive"}:
        raise ValueError("不支持的渠道管理范围状态。")

    start_stake_text = _clean_text(start_stake_text)
    end_stake_text = _clean_text(end_stake_text)
    start_stake_value = (
        None if start_stake_value is None else float(start_stake_value)
    )
    end_stake_value = (
        None if end_stake_value is None else float(end_stake_value)
    )

    _validate_range(
        range_mode,
        start_stake_text,
        start_stake_value,
        end_stake_text,
        end_stake_value,
    )

    master_key = _clean_text(master_key)
    management_scope_uid = _clean_text(management_scope_uid)

    with database.get_connection() as connection:
        canal = connection.execute(
            """
            SELECT id
            FROM canal_units
            WHERE id = ?
            """,
            (int(canal_unit_id),),
        ).fetchone()

        if canal is None:
            raise ValueError("指定渠系不存在。")

        office = connection.execute(
            """
            SELECT id, unit_type
            FROM organization_units
            WHERE id = ?
            """,
            (int(organization_unit_id),),
        ).fetchone()

        if office is None:
            raise ValueError("指定管理单位不存在。")

        if office["unit_type"] != "water_office":
            raise ValueError(
                "渠道管理范围只能关联末级管理单位。"
            )

        if master_key:
            expected_uid = deterministic_master_uid(
                "canal_management_scope",
                master_key,
            )
            if management_scope_uid and management_scope_uid != expected_uid:
                raise ValueError(
                    "正式管理范围 UID 与 master_key 不一致。"
                )
            management_scope_uid = expected_uid
        elif not management_scope_uid:
            management_scope_uid = uuid4().hex

        cursor = connection.execute(
            """
            INSERT INTO canal_management_scopes (
                management_scope_uid,
                master_key,
                canal_unit_id,
                organization_unit_id,
                range_mode,
                start_stake_text,
                start_stake_value,
                end_stake_text,
                end_stake_value,
                sort_order,
                status,
                description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                management_scope_uid,
                master_key,
                int(canal_unit_id),
                int(organization_unit_id),
                range_mode,
                start_stake_text,
                start_stake_value,
                end_stake_text,
                end_stake_value,
                int(sort_order or 0),
                status,
                _clean_text(description),
            ),
        )

        row = connection.execute(
            _scope_select_sql()
            + " WHERE cms.id = ?",
            (int(cursor.lastrowid),),
        ).fetchone()

    return dict(row)


def get_canal_management_scope(management_scope_uid):
    # 按稳定 UID 获取单条渠道管理范围。
    # 身份查询不按 active / inactive 过滤，以支持维护已停用记录。
    management_scope_uid = _clean_text(
        management_scope_uid
    )

    if not management_scope_uid:
        return None

    with database.get_connection() as connection:
        row = connection.execute(
            _scope_select_sql()
            + " WHERE cms.management_scope_uid = ?",
            (
                management_scope_uid,
            ),
        ).fetchone()

    if row is None:
        return None

    return dict(
        row
    )


def get_management_scopes_for_canal(canal_unit_id, *, active_only=True):
    sql = _scope_select_sql() + " WHERE cms.canal_unit_id = ?"
    params = [int(canal_unit_id)]
    if active_only:
        sql += " AND cms.status = 'active'"
    sql += " ORDER BY cms.sort_order, office.sort_order, cms.id"

    with database.get_connection() as connection:
        rows = connection.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def get_management_scopes_for_organization(
    organization_unit_id,
    *,
    active_only=True,
):
    sql = _scope_select_sql() + " WHERE cms.organization_unit_id = ?"
    params = [int(organization_unit_id)]
    if active_only:
        sql += " AND cms.status = 'active'"
    sql += " ORDER BY canal.sort_order, cms.sort_order, cms.id"

    with database.get_connection() as connection:
        rows = connection.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def get_management_scopes_for_relation(
    canal_unit_id,
    organization_unit_id,
    *,
    active_only=True,
):
    sql = (
        _scope_select_sql()
        + " WHERE cms.canal_unit_id = ? AND cms.organization_unit_id = ?"
    )
    params = [int(canal_unit_id), int(organization_unit_id)]
    if active_only:
        sql += " AND cms.status = 'active'"
    sql += " ORDER BY cms.sort_order, cms.id"

    with database.get_connection() as connection:
        rows = connection.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def organization_manages_canal(organization_unit_id, canal_unit_id):
    with database.get_connection() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM canal_management_scopes
            WHERE canal_unit_id = ?
              AND organization_unit_id = ?
              AND status = 'active'
            LIMIT 1
            """,
            (int(canal_unit_id), int(organization_unit_id)),
        ).fetchone()
    return row is not None


def find_management_scope_for_stake(
    canal_unit_id,
    stake_value,
    *,
    organization_unit_id=None,
):
    """
    尝试按桩号判定管理范围。

    status:
    matched / ambiguous / unresolved / not_managed

    segment_unknown 永远不依据桩号猜归属。
    """
    value = float(stake_value)
    sql = """
        SELECT *
        FROM canal_management_scopes
        WHERE canal_unit_id = ?
          AND status = 'active'
    """
    params = [int(canal_unit_id)]

    if organization_unit_id is not None:
        sql += " AND organization_unit_id = ?"
        params.append(int(organization_unit_id))

    sql += " ORDER BY sort_order, id"

    with database.get_connection() as connection:
        rows = [
            dict(row)
            for row in connection.execute(sql, tuple(params)).fetchall()
        ]

    exact = []
    unknown = []

    for row in rows:
        mode = row["range_mode"]
        if mode == RANGE_MODE_WHOLE:
            exact.append(row)
        elif mode == RANGE_MODE_SEGMENT_KNOWN:
            if (
                float(row["start_stake_value"])
                <= value
                <= float(row["end_stake_value"])
            ):
                exact.append(row)
        elif mode == RANGE_MODE_SEGMENT_UNKNOWN:
            unknown.append(row)

    if len(exact) == 1:
        return {
            "status": "matched",
            "scope": exact[0],
            "candidate_scopes": exact,
        }

    if len(exact) > 1:
        return {
            "status": "ambiguous",
            "scope": None,
            "candidate_scopes": exact,
        }

    if unknown:
        return {
            "status": "unresolved",
            "scope": None,
            "candidate_scopes": unknown,
        }

    return {
        "status": "not_managed",
        "scope": None,
        "candidate_scopes": [],
    }


def get_managed_canals_for_organization(
    organization_unit_id,
    *,
    active_only=True,
):
    """
    获取某末级管理单位当前可管理/调查的渠道集合。

    Stage 14.2 起，本函数以 canal_management_scopes
    作为“管理单位 -> 渠道”的事实源，不再读取
    canal_units.organization_unit_id。

    同一管理单位可能在同一渠道上存在多个分段管理范围，
    因此这里按 CanalUnit 去重；调查录入当前只选择渠道，
    具体管理段将在后续任务范围阶段接入。

    active_only=True：
        新增调查使用，只返回启用的管理关系和启用渠道。

    active_only=False：
        历史记录回填使用，允许返回已停用关系/渠道，
        避免管理关系调整后无法打开既有调查。
    """

    try:
        organization_unit_id = int(
            organization_unit_id
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "organization_unit_id 必须是有效正整数。"
        ) from error

    if organization_unit_id <= 0:
        raise ValueError(
            "organization_unit_id 必须是有效正整数。"
        )

    sql = """
        SELECT DISTINCT
            canal.id,
            canal.parent_id,
            canal.name,
            canal.canal_level,
            canal.status,
            canal.description,
            canal.canal_unit_uid,
            canal.master_key,
            canal.sort_order

        FROM canal_management_scopes
            AS cms

        JOIN canal_units AS canal
            ON canal.id
                = cms.canal_unit_id

        WHERE
            cms.organization_unit_id = ?
    """

    parameters = [
        organization_unit_id,
    ]

    if active_only:
        sql += """
          AND cms.status = 'active'
          AND canal.status = 'active'
        """

    sql += """
        ORDER BY
            canal.sort_order,
            canal.id
    """

    with database.get_connection() as connection:
        rows = connection.execute(
            sql,
            tuple(
                parameters
            ),
        ).fetchall()

    return [
        dict(
            row
        )
        for row in rows
    ]
