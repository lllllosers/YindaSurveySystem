from __future__ import annotations

from hashlib import sha256

import database


MASTER_IDENTITY_NAMESPACE = (
    "yinda-survey-official-master-v1"
)

_OFFICIAL_MASTER_IDENTITY_SPECS = (
    (
        "organization",
        "organization_units",
        "organization_unit_uid",
    ),
    (
        "canal",
        "canal_units",
        "canal_unit_uid",
    ),
)


def deterministic_master_uid(
    entity_kind,
    master_key,
):
    """
    为“甲方正式主数据”生成跨数据库一致的稳定 UID。

    Stage 08 的随机 UID 适用于普通业务实体；
    但 organization_units / canal_units 中带 master_key 的正式
    参考主数据会在多台电脑上分别初始化，如果继续随机生成，
    同一个水管所/渠道在不同电脑上的 UID 会不同，无法可靠交换
    .ydtask / .ydresult。

    因此仅对带 master_key 的官方主数据采用确定性 UID。
    普通人工新增节点仍保持原有随机 UID 机制。
    """

    entity_kind = str(
        entity_kind or ""
    ).strip().lower()

    master_key = str(
        master_key or ""
    ).strip()

    if entity_kind not in {
        "organization",
        "canal",
    }:
        raise ValueError(
            "不支持的正式主数据实体类型。"
        )

    if not master_key:
        raise ValueError(
            "master_key 不能为空。"
        )

    payload = (
        f"{MASTER_IDENTITY_NAMESPACE}:"
        f"{entity_kind}:"
        f"{master_key}"
    ).encode("utf-8")

    return (
        sha256(payload)
        .hexdigest()[:32]
    )


def _build_sync_plan(
    connection,
    *,
    entity_kind,
    table_name,
    uid_column,
):
    rows = connection.execute(
        f"""
        SELECT
            id,
            master_key,
            {uid_column} AS current_uid
        FROM {table_name}
        WHERE master_key IS NOT NULL
          AND trim(master_key) <> ''
        ORDER BY id
        """
    ).fetchall()

    plan = []

    target_uids = set()

    for row in rows:
        target_uid = (
            deterministic_master_uid(
                entity_kind,
                row["master_key"],
            )
        )

        if target_uid in target_uids:
            raise RuntimeError(
                "正式主数据确定性 UID 发生重复，"
                f"同步已停止：{table_name}。"
            )

        target_uids.add(
            target_uid
        )

        collision = connection.execute(
            f"""
            SELECT
                id,
                master_key
            FROM {table_name}
            WHERE {uid_column} = ?
              AND id != ?
            LIMIT 1
            """,
            (
                target_uid,
                int(row["id"]),
            ),
        ).fetchone()

        if collision is not None:
            raise RuntimeError(
                "正式主数据目标 UID 已被其他记录占用，"
                "同步已停止："
                f"{table_name}.{row['master_key']}。"
            )

        current_uid = str(
            row["current_uid"]
            or ""
        ).strip()

        if current_uid == target_uid:
            continue

        plan.append(
            {
                "id": int(row["id"]),
                "master_key": (
                    row["master_key"]
                ),
                "old_uid": (
                    current_uid
                    or None
                ),
                "new_uid": (
                    target_uid
                ),
            }
        )

    return plan


def synchronize_official_master_identities():
    """
    将正式组织机构/渠系的 UID 同步为确定性值。

    特性：
    - 只处理 master_key 非空的官方主数据；
    - 不改变 SQLite 自增 id；
    - EngineeringAsset / SurveyRecord 当前通过整数 FK 关联，
      因此本迁移不会破坏现有本地业务关系；
    - 普通人工新增组织/渠系节点不受影响；
    - 可重复执行；
    - 在同一事务内临时移除 UID 不可变触发器，完成迁移后
      立即调用数据库原有稳定身份安装逻辑恢复保护。
    """

    total_rows = 0
    changed_rows = 0
    details = {}

    with database.get_connection() as connection:
        plans = {}

        for (
            entity_kind,
            table_name,
            uid_column,
        ) in _OFFICIAL_MASTER_IDENTITY_SPECS:
            plan = _build_sync_plan(
                connection,
                entity_kind=(
                    entity_kind
                ),
                table_name=(
                    table_name
                ),
                uid_column=(
                    uid_column
                ),
            )

            count_row = connection.execute(
                f"""
                SELECT COUNT(*) AS count_value
                FROM {table_name}
                WHERE master_key IS NOT NULL
                  AND trim(master_key) <> ''
                """
            ).fetchone()

            row_count = int(
                count_row["count_value"]
            )

            total_rows += row_count

            details[
                table_name
            ] = {
                "official_row_count": (
                    row_count
                ),
                "changed_row_count": (
                    len(plan)
                ),
            }

            plans[
                (
                    table_name,
                    uid_column,
                )
            ] = plan

        if any(
            plans.values()
        ):
            # Stage 08 对稳定 UID 设置了不可变触发器。
            # 这里属于一次受控迁移，只临时移除 organization/canal
            # 两张正式主数据表对应的不可变触发器。
            for (
                table_name,
                uid_column,
            ) in plans:
                trigger_name = (
                    f"trg_{table_name}_"
                    f"{uid_column}_immutable"
                )

                connection.execute(
                    (
                        "DROP TRIGGER IF EXISTS "
                        f"{trigger_name}"
                    )
                )

            for (
                table_name,
                uid_column,
            ), plan in plans.items():
                for item in plan:
                    connection.execute(
                        f"""
                        UPDATE {table_name}
                        SET {uid_column} = ?
                        WHERE id = ?
                        """,
                        (
                            item["new_uid"],
                            item["id"],
                        ),
                    )

                    changed_rows += 1

            # 复用 Stage 08 的既有逻辑恢复唯一索引、自动生成和
            # UID 不可变保护，避免在本服务复制第二份触发器事实。
            database._ensure_stable_identity_schema(
                connection
            )

    return {
        "official_row_count": (
            total_rows
        ),
        "changed_row_count": (
            changed_rows
        ),
        "already_synchronized": (
            changed_rows == 0
        ),
        "details": details,
    }
