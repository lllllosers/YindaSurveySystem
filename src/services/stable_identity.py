from __future__ import annotations

import database


ENTITY_IDENTITY_SPECS = {
    "project": (
        "projects",
        "project_uid",
    ),
    "survey_batch": (
        "survey_batches",
        "survey_batch_uid",
    ),
    "organization_unit": (
        "organization_units",
        "organization_unit_uid",
    ),
    "canal_unit": (
        "canal_units",
        "canal_unit_uid",
    ),
    "engineering_asset": (
        "engineering_assets",
        "engineering_asset_uid",
    ),
    "survey_record": (
        "survey_records",
        "survey_record_uid",
    ),
}


def _get_spec(
    entity_type,
):
    key = str(
        entity_type or ""
    ).strip()

    spec = ENTITY_IDENTITY_SPECS.get(
        key
    )

    if spec is None:
        raise ValueError(
            "不支持的稳定身份类型："
            f"{entity_type}"
        )

    return spec


def get_entity_uid(
    entity_type,
    local_id,
):
    """
    根据本机 SQLite 整数主键取得跨数据库稳定 UID。
    """

    table_name, uid_column = (
        _get_spec(
            entity_type
        )
    )

    try:
        local_id = int(local_id)
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "本地主键必须是整数。"
        ) from error

    with database.get_connection() as connection:
        row = connection.execute(
            (
                f"SELECT {uid_column} AS uid "
                f"FROM {table_name} "
                "WHERE id = ?"
            ),
            (local_id,),
        ).fetchone()

    if row is None:
        return None

    uid = str(
        row["uid"]
        or ""
    ).strip()

    return uid or None


def require_entity_uid(
    entity_type,
    local_id,
):
    """
    与 get_entity_uid 相同，但不存在实体或 UID 时直接报错。
    """

    uid = get_entity_uid(
        entity_type,
        local_id,
    )

    if uid is None:
        raise ValueError(
            "没有找到对应的稳定身份。"
        )

    return uid


def resolve_entity_id(
    entity_type,
    stable_uid,
):
    """
    根据跨数据库稳定 UID 解析当前数据库中的本地整数主键。

    这是后续任务包/结果包导入合并时的基础能力。
    """

    table_name, uid_column = (
        _get_spec(
            entity_type
        )
    )

    stable_uid = str(
        stable_uid or ""
    ).strip()

    if not stable_uid:
        raise ValueError(
            "稳定 UID 不能为空。"
        )

    with database.get_connection() as connection:
        row = connection.execute(
            (
                "SELECT id "
                f"FROM {table_name} "
                f"WHERE {uid_column} = ?"
            ),
            (stable_uid,),
        ).fetchone()

    if row is None:
        return None

    return int(
        row["id"]
    )


def get_identity_pair(
    entity_type,
    *,
    local_id=None,
    stable_uid=None,
):
    """
    返回：
        {
            "local_id": ...,
            "stable_uid": ...
        }

    至少提供 local_id 或 stable_uid 其中之一。
    如果两者都提供，会检查是否指向同一实体。
    """

    if (
        local_id is None
        and stable_uid is None
    ):
        raise ValueError(
            "必须提供 local_id "
            "或 stable_uid。"
        )

    resolved_local_id = None
    resolved_uid = None

    if local_id is not None:
        try:
            resolved_local_id = int(
                local_id
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise ValueError(
                "本地主键必须是整数。"
            ) from error

        resolved_uid = (
            get_entity_uid(
                entity_type,
                resolved_local_id,
            )
        )

        if resolved_uid is None:
            raise ValueError(
                "没有找到指定本地实体。"
            )

    if stable_uid is not None:
        clean_uid = str(
            stable_uid
        ).strip()

        if not clean_uid:
            raise ValueError(
                "稳定 UID 不能为空。"
            )

        uid_local_id = (
            resolve_entity_id(
                entity_type,
                clean_uid,
            )
        )

        if uid_local_id is None:
            raise ValueError(
                "没有找到指定稳定 UID。"
            )

        if (
            resolved_local_id is not None
            and uid_local_id
            != resolved_local_id
        ):
            raise ValueError(
                "local_id 与 stable_uid "
                "不属于同一实体。"
            )

        resolved_local_id = (
            uid_local_id
        )
        resolved_uid = clean_uid

    return {
        "local_id": (
            resolved_local_id
        ),
        "stable_uid": (
            resolved_uid
        ),
    }
