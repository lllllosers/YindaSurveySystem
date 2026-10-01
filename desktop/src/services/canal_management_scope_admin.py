from __future__ import annotations

import database

from services.canal_management_scope import (
    RANGE_MODE_SEGMENT_KNOWN,
    RANGE_MODE_SEGMENT_UNKNOWN,
    RANGE_MODE_WHOLE,
    create_canal_management_scope,
    get_canal_management_scope,
    get_management_scopes_for_canal,
)

VALID_RANGE_MODES = {
    RANGE_MODE_WHOLE,
    RANGE_MODE_SEGMENT_KNOWN,
    RANGE_MODE_SEGMENT_UNKNOWN,
}

VALID_STATUSES = {
    "active",
    "inactive",
}


def _normalize_text(
    value,
):
    if value is None:
        return None

    text = str(
        value
    ).strip()

    return text or None


def _normalize_float(
    value,
):
    if value is None:
        return None

    return float(
        value
    )


def _validate_range_payload(
    *,
    range_mode,
    start_stake_text,
    start_stake_value,
    end_stake_text,
    end_stake_value,
):
    if range_mode not in VALID_RANGE_MODES:
        raise ValueError(
            "不支持的渠道管理范围类型。"
        )

    if range_mode == RANGE_MODE_SEGMENT_KNOWN:
        if (
            start_stake_value is None
            or end_stake_value is None
        ):
            raise ValueError(
                "已知分段必须填写起止桩号。"
            )

        if (
            float(start_stake_value)
            > float(end_stake_value)
        ):
            raise ValueError(
                "起始桩号不能大于终止桩号。"
            )

        return

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
            "全渠或边界未知分段"
            "不能保存起止桩号。"
        )


def _validate_office(
    connection,
    organization_unit_id,
):
    row = connection.execute(
        """
        SELECT
            id,
            unit_type,
            status
        FROM organization_units
        WHERE id = ?
        """,
        (
            int(
                organization_unit_id
            ),
        ),
    ).fetchone()

    if row is None:
        raise ValueError(
            "指定管理单位不存在。"
        )

    if row[
        "unit_type"
    ] != "water_office":
        raise ValueError(
            "渠道管理范围只能关联末级管理单位。"
        )

    return row


def _validate_active_coexistence(
    connection,
    *,
    canal_unit_id,
    range_mode,
    status,
    exclude_scope_id=None,
):
    """
    管理范围维护层阻止明显矛盾：
    - active whole 表示整条渠道由一个管理单位负责，
      因而不能与同渠其他 active 范围并存；
    - active 分段也不能与已有 active whole 并存。

    已知分段之间的重叠本阶段不自动阻断，
    留给后续边界/冲突检查显式处理。
    """

    if status != "active":
        return

    sql = """
        SELECT
            id,
            range_mode
        FROM canal_management_scopes
        WHERE canal_unit_id = ?
          AND status = 'active'
    """

    parameters = [
        int(
            canal_unit_id
        )
    ]

    if exclude_scope_id is not None:
        sql += """
          AND id != ?
        """

        parameters.append(
            int(
                exclude_scope_id
            )
        )

    rows = connection.execute(
        sql,
        tuple(
            parameters
        ),
    ).fetchall()

    if not rows:
        return

    if range_mode == RANGE_MODE_WHOLE:
        raise ValueError(
            "当前渠道已经存在启用的管理范围。"
            "“全渠管理”不能与其他启用范围并存；"
            "请先停用原范围。"
        )

    if any(
        row[
            "range_mode"
        ]
        == RANGE_MODE_WHOLE
        for row in rows
    ):
        raise ValueError(
            "当前渠道已经存在启用的“全渠管理”关系。"
            "请先停用该关系，再配置分段管理。"
        )


def create_management_scope(
    *,
    canal_unit_id,
    organization_unit_id,
    range_mode,
    start_stake_text=None,
    start_stake_value=None,
    end_stake_text=None,
    end_stake_value=None,
    sort_order=0,
    description=None,
):
    start_stake_text = (
        _normalize_text(
            start_stake_text
        )
    )
    end_stake_text = (
        _normalize_text(
            end_stake_text
        )
    )
    start_stake_value = (
        _normalize_float(
            start_stake_value
        )
    )
    end_stake_value = (
        _normalize_float(
            end_stake_value
        )
    )

    _validate_range_payload(
        range_mode=range_mode,
        start_stake_text=start_stake_text,
        start_stake_value=start_stake_value,
        end_stake_text=end_stake_text,
        end_stake_value=end_stake_value,
    )

    with database.get_connection() as connection:
        _validate_office(
            connection,
            organization_unit_id,
        )

        _validate_active_coexistence(
            connection,
            canal_unit_id=canal_unit_id,
            range_mode=range_mode,
            status="active",
        )

    return create_canal_management_scope(
        canal_unit_id=canal_unit_id,
        organization_unit_id=organization_unit_id,
        range_mode=range_mode,
        start_stake_text=start_stake_text,
        start_stake_value=start_stake_value,
        end_stake_text=end_stake_text,
        end_stake_value=end_stake_value,
        sort_order=sort_order,
        status="active",
        description=description,
    )


def update_management_scope(
    management_scope_uid,
    *,
    organization_unit_id,
    range_mode,
    start_stake_text=None,
    start_stake_value=None,
    end_stake_text=None,
    end_stake_value=None,
    sort_order=None,
    description=None,
):
    current = get_canal_management_scope(
        management_scope_uid
    )

    if current is None:
        raise ValueError(
            "没有找到指定渠道管理范围。"
        )

    start_stake_text = (
        _normalize_text(
            start_stake_text
        )
    )
    end_stake_text = (
        _normalize_text(
            end_stake_text
        )
    )
    start_stake_value = (
        _normalize_float(
            start_stake_value
        )
    )
    end_stake_value = (
        _normalize_float(
            end_stake_value
        )
    )

    _validate_range_payload(
        range_mode=range_mode,
        start_stake_text=start_stake_text,
        start_stake_value=start_stake_value,
        end_stake_text=end_stake_text,
        end_stake_value=end_stake_value,
    )

    current_master_key = (
        _normalize_text(
            current[
                "master_key"
            ]
        )
    )

    if (
        current_master_key
        and int(
            organization_unit_id
        )
        != int(
            current[
                "organization_unit_id"
            ]
        )
    ):
        raise ValueError(
            "正式主数据管理范围不能直接更换管理单位。"
            "如业务关系发生变化，请停用原范围后新增新范围。"
        )

    with database.get_connection() as connection:
        _validate_office(
            connection,
            organization_unit_id,
        )

        _validate_active_coexistence(
            connection,
            canal_unit_id=(
                current[
                    "canal_unit_id"
                ]
            ),
            range_mode=range_mode,
            status=(
                current[
                    "status"
                ]
            ),
            exclude_scope_id=(
                current[
                    "id"
                ]
            ),
        )

        connection.execute(
            """
            UPDATE canal_management_scopes
            SET
                organization_unit_id = ?,
                range_mode = ?,
                start_stake_text = ?,
                start_stake_value = ?,
                end_stake_text = ?,
                end_stake_value = ?,
                sort_order = ?,
                description = ?,
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE management_scope_uid = ?
            """,
            (
                int(
                    organization_unit_id
                ),
                range_mode,
                start_stake_text,
                start_stake_value,
                end_stake_text,
                end_stake_value,
                int(
                    current[
                        "sort_order"
                    ]
                    if sort_order is None
                    else sort_order
                ),
                _normalize_text(
                    description
                ),
                management_scope_uid,
            ),
        )

    return get_canal_management_scope(
        management_scope_uid
    )


def set_management_scope_status(
    management_scope_uid,
    status,
):
    status = str(
        status or ""
    ).strip()

    if status not in VALID_STATUSES:
        raise ValueError(
            "不支持的渠道管理范围状态。"
        )

    current = get_canal_management_scope(
        management_scope_uid
    )

    if current is None:
        raise ValueError(
            "没有找到指定渠道管理范围。"
        )

    with database.get_connection() as connection:
        _validate_active_coexistence(
            connection,
            canal_unit_id=(
                current[
                    "canal_unit_id"
                ]
            ),
            range_mode=(
                current[
                    "range_mode"
                ]
            ),
            status=status,
            exclude_scope_id=(
                current[
                    "id"
                ]
            ),
        )

        connection.execute(
            """
            UPDATE canal_management_scopes
            SET
                status = ?,
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE management_scope_uid = ?
            """,
            (
                status,
                management_scope_uid,
            ),
        )

    return get_canal_management_scope(
        management_scope_uid
    )


def delete_management_scope(
    management_scope_uid,
):
    current = get_canal_management_scope(
        management_scope_uid
    )

    if current is None:
        raise ValueError(
            "没有找到指定渠道管理范围。"
        )

    if _normalize_text(
        current[
            "master_key"
        ]
    ):
        raise ValueError(
            "正式主数据管理范围不能物理删除。"
            "如已不再适用，请改为停用。"
        )

    with database.get_connection() as connection:
        connection.execute(
            """
            DELETE FROM canal_management_scopes
            WHERE management_scope_uid = ?
            """,
            (
                management_scope_uid,
            ),
        )


def get_canal_management_summary_map(
    *,
    active_only=True,
):
    sql = """
        SELECT
            cms.canal_unit_id,
            cms.range_mode,
            cms.start_stake_text,
            cms.start_stake_value,
            cms.end_stake_text,
            cms.end_stake_value,
            cms.status,
            office.name
                AS organization_name,
            office.sort_order
                AS organization_sort_order,
            cms.sort_order,
            cms.id

        FROM canal_management_scopes
            AS cms

        JOIN organization_units
            AS office
            ON office.id
                = cms.organization_unit_id
    """

    parameters = []

    if active_only:
        sql += """
        WHERE cms.status = 'active'
        """

    sql += """
        ORDER BY
            cms.canal_unit_id,
            cms.sort_order,
            office.sort_order,
            cms.id
    """

    with database.get_connection() as connection:
        rows = [
            dict(
                row
            )
            for row in connection.execute(
                sql,
                tuple(
                    parameters
                ),
            ).fetchall()
        ]

    grouped = {}

    for row in rows:
        canal_id = int(
            row[
                "canal_unit_id"
            ]
        )

        name = str(
            row[
                "organization_name"
            ]
            or ""
        ).strip()

        mode = row[
            "range_mode"
        ]

        if mode == RANGE_MODE_WHOLE:
            detail = "全渠"

        elif mode == RANGE_MODE_SEGMENT_UNKNOWN:
            detail = "分段/边界未知"

        else:
            start = (
                row[
                    "start_stake_text"
                ]
                or str(
                    row[
                        "start_stake_value"
                    ]
                )
            )

            end = (
                row[
                    "end_stake_text"
                ]
                or str(
                    row[
                        "end_stake_value"
                    ]
                )
            )

            detail = (
                f"{start}～{end}"
            )

        if (
            not active_only
            and row[
                "status"
            ]
            != "active"
        ):
            detail += "，停用"

        grouped.setdefault(
            canal_id,
            [],
        ).append(
            f"{name}（{detail}）"
        )

    return {
        canal_id: "；".join(
            parts
        )
        for (
            canal_id,
            parts,
        ) in grouped.items()
    }


def get_management_scopes_for_admin(
    canal_unit_id,
):
    return get_management_scopes_for_canal(
        canal_unit_id,
        active_only=False,
    )
