from __future__ import annotations

import json

import database

from services.canal_management_scope import (
    RANGE_MODE_WHOLE,
    ensure_canal_management_scope_schema,
)
from services.master_identity import (
    deterministic_master_uid,
)
from services.official_master_data import (
    OFFICIAL_CANALS,
)


OFFICIAL_CANAL_MANAGEMENT_SCOPE_VERSION = (
    "2026-09-official-canal-management-scope-v1"
)

OFFICIAL_CANAL_MANAGEMENT_SCOPE_SOURCE = (
    "由 OFFICIAL_CANALS 中已确认的 organization_master_key "
    "直接生成；骨干干渠/分干渠分段管理关系待甲方确认后补充"
)


# 后续甲方一旦明确“某骨干渠由哪些所分段管理”，
# 在这里增加明确的 segment_unknown / segment_known 规格。
# 当前不得根据组织层级或经验自行猜测。
OFFICIAL_SEGMENT_SCOPE_SPECS = ()


def _whole_scope_master_key(
    canal_master_key,
    organization_master_key,
):
    return (
        "CMS-"
        f"{canal_master_key}-"
        f"{organization_master_key}"
    )


def get_confirmed_official_scope_specs():
    """
    返回当前已经有明确依据的正式渠道管理关系。

    Stage 14.1 当前事实来源：
    - 支渠/分支渠既有正式管理单位归属 -> whole；
    - 干渠/分干渠没有明确分段单位时不生成关系；
    - 后续确认的骨干渠分段关系通过
      OFFICIAL_SEGMENT_SCOPE_SPECS 显式补充。

    注意：
    物理 CanalUnit 不承载管理归属；正式关系直接写入 canal_management_scopes。
    """

    specs = []

    for canal in OFFICIAL_CANALS:
        organization_master_key = (
            canal.get(
                "organization_master_key"
            )
        )

        if not organization_master_key:
            continue

        canal_master_key = (
            canal[
                "master_key"
            ]
        )

        specs.append(
            {
                "master_key": (
                    _whole_scope_master_key(
                        canal_master_key,
                        organization_master_key,
                    )
                ),
                "canal_master_key": (
                    canal_master_key
                ),
                "organization_master_key": (
                    organization_master_key
                ),
                "range_mode": (
                    RANGE_MODE_WHOLE
                ),
                "start_stake_text": None,
                "start_stake_value": None,
                "end_stake_text": None,
                "end_stake_value": None,
                "sort_order": int(
                    canal.get(
                        "sort_order",
                        0,
                    )
                    or 0
                ),
                "description": None,
            }
        )

    specs.extend(
        dict(
            spec
        )
        for spec in (
            OFFICIAL_SEGMENT_SCOPE_SPECS
        )
    )

    return tuple(
        specs
    )


def _load_reference_maps(
    connection,
):
    canal_rows = connection.execute(
        """
        SELECT
            id,
            master_key,
            name
        FROM canal_units
        WHERE master_key IS NOT NULL
          AND trim(master_key) <> ''
        """
    ).fetchall()

    organization_rows = connection.execute(
        """
        SELECT
            id,
            master_key,
            name,
            unit_type
        FROM organization_units
        WHERE master_key IS NOT NULL
          AND trim(master_key) <> ''
        """
    ).fetchall()

    canal_map = {
        row[
            "master_key"
        ]: dict(
            row
        )
        for row in canal_rows
    }

    organization_map = {
        row[
            "master_key"
        ]: dict(
            row
        )
        for row in organization_rows
    }

    return (
        canal_map,
        organization_map,
    )


def _seed_one_scope(
    connection,
    spec,
    canal_map,
    organization_map,
):
    canal = canal_map.get(
        spec[
            "canal_master_key"
        ]
    )

    if canal is None:
        raise RuntimeError(
            "正式管理范围引用了不存在的渠系："
            f"{spec['canal_master_key']}。"
        )

    organization = (
        organization_map.get(
            spec[
                "organization_master_key"
            ]
        )
    )

    if organization is None:
        raise RuntimeError(
            "正式管理范围引用了不存在的管理单位："
            f"{spec['organization_master_key']}。"
        )

    if (
        organization[
            "unit_type"
        ]
        != "water_office"
    ):
        raise RuntimeError(
            "正式渠道管理范围必须关联末级管理单位："
            f"{spec['organization_master_key']}。"
        )

    master_key = (
        spec[
            "master_key"
        ]
    )

    expected_uid = (
        deterministic_master_uid(
            "canal_management_scope",
            master_key,
        )
    )

    existing = connection.execute(
        """
        SELECT
            id,
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
            status
        FROM canal_management_scopes
        WHERE master_key = ?
        """,
        (
            master_key,
        ),
    ).fetchone()

    if existing is not None:
        expected_values = (
            int(
                canal[
                    "id"
                ]
            ),
            int(
                organization[
                    "id"
                ]
            ),
            spec[
                "range_mode"
            ],
            spec.get(
                "start_stake_text"
            ),
            spec.get(
                "start_stake_value"
            ),
            spec.get(
                "end_stake_text"
            ),
            spec.get(
                "end_stake_value"
            ),
        )

        actual_values = (
            int(
                existing[
                    "canal_unit_id"
                ]
            ),
            int(
                existing[
                    "organization_unit_id"
                ]
            ),
            existing[
                "range_mode"
            ],
            existing[
                "start_stake_text"
            ],
            existing[
                "start_stake_value"
            ],
            existing[
                "end_stake_text"
            ],
            existing[
                "end_stake_value"
            ],
        )

        if (
            existing[
                "management_scope_uid"
            ]
            != expected_uid
            or actual_values
            != expected_values
        ):
            raise RuntimeError(
                "正式渠道管理范围与现有稳定数据冲突："
                f"{master_key}。"
            )

        return (
            int(
                existing[
                    "id"
                ]
            ),
            "existing",
        )

    candidates = connection.execute(
        """
        SELECT
            id,
            management_scope_uid,
            master_key,
            range_mode,
            start_stake_text,
            start_stake_value,
            end_stake_text,
            end_stake_value
        FROM canal_management_scopes
        WHERE canal_unit_id = ?
          AND organization_unit_id = ?
          AND range_mode = ?
        ORDER BY id
        """,
        (
            int(
                canal[
                    "id"
                ]
            ),
            int(
                organization[
                    "id"
                ]
            ),
            spec[
                "range_mode"
            ],
        ),
    ).fetchall()

    exact_candidates = []

    for candidate in candidates:
        if (
            candidate[
                "start_stake_text"
            ]
            == spec.get(
                "start_stake_text"
            )
            and candidate[
                "start_stake_value"
            ]
            == spec.get(
                "start_stake_value"
            )
            and candidate[
                "end_stake_text"
            ]
            == spec.get(
                "end_stake_text"
            )
            and candidate[
                "end_stake_value"
            ]
            == spec.get(
                "end_stake_value"
            )
        ):
            exact_candidates.append(
                candidate
            )

    if len(
        exact_candidates
    ) > 1:
        raise RuntimeError(
            "正式渠道管理范围存在多条"
            "无法安全接管的候选记录："
            f"{master_key}。"
        )

    if exact_candidates:
        candidate = (
            exact_candidates[0]
        )

        # Stage 14.0 对正式渠系 + 正式管理单位生成的迁移记录
        # 已使用同一个确定性 UID。这里仅允许接管稳定身份完全一致
        # 的记录，避免突破 UID 不可变约束。
        if (
            candidate[
                "management_scope_uid"
            ]
            != expected_uid
        ):
            raise RuntimeError(
                "候选渠道管理范围 UID "
                "不是预期的正式稳定 UID，"
                "拒绝自动接管："
                f"{master_key}。"
            )

        if (
            candidate[
                "master_key"
            ]
            not in (
                None,
                "",
                master_key,
            )
        ):
            raise RuntimeError(
                "候选渠道管理范围已绑定"
                "其他 master_key，拒绝接管："
                f"{master_key}。"
            )

        connection.execute(
            """
            UPDATE canal_management_scopes
            SET
                master_key = ?,
                sort_order = ?,
                status = 'active',
                description = CASE
                    WHEN description IS NULL
                      OR trim(description) = ''
                    THEN ?
                    ELSE description
                END,
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id = ?
            """,
            (
                master_key,
                int(
                    spec.get(
                        "sort_order",
                        0,
                    )
                    or 0
                ),
                spec.get(
                    "description"
                ),
                int(
                    candidate[
                        "id"
                    ]
                ),
            ),
        )

        return (
            int(
                candidate[
                    "id"
                ]
            ),
            "adopted",
        )

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
        VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            'active', ?
        )
        """,
        (
            expected_uid,
            master_key,
            int(
                canal[
                    "id"
                ]
            ),
            int(
                organization[
                    "id"
                ]
            ),
            spec[
                "range_mode"
            ],
            spec.get(
                "start_stake_text"
            ),
            spec.get(
                "start_stake_value"
            ),
            spec.get(
                "end_stake_text"
            ),
            spec.get(
                "end_stake_value"
            ),
            int(
                spec.get(
                    "sort_order",
                    0,
                )
                or 0
            ),
            spec.get(
                "description"
            ),
        ),
    )

    return (
        int(
            cursor.lastrowid
        ),
        "created",
    )


def seed_official_canal_management_scopes():
    """
    将“已确认”的渠道管理关系登记为正式主数据。

    该种子与组织/渠系种子分开版本化：
    - 不修改 CanalUnit 的物理渠系身份；
    - 不猜测骨干渠经过哪些所；
    - 已有正式支渠/分支渠归属登记为 whole；
    - 后续骨干渠分段资料可独立追加版本；
    - 种子成功后重复启动不会覆盖人工补充信息。
    """

    ensure_canal_management_scope_schema()

    specs = (
        get_confirmed_official_scope_specs()
    )

    with database.get_connection() as connection:
        already = connection.execute(
            """
            SELECT seed_key
            FROM master_data_seed_history
            WHERE seed_key = ?
            """,
            (
                OFFICIAL_CANAL_MANAGEMENT_SCOPE_VERSION,
            ),
        ).fetchone()

        if already is not None:
            return {
                "applied": False,
                "already_applied": True,
                "seed_key": (
                    OFFICIAL_CANAL_MANAGEMENT_SCOPE_VERSION
                ),
                "scope_count": len(
                    specs
                ),
            }

        (
            canal_map,
            organization_map,
        ) = _load_reference_maps(
            connection
        )

        counters = {
            "scope_created": 0,
            "scope_adopted": 0,
            "scope_existing": 0,
        }

        for spec in specs:
            (
                _scope_id,
                action,
            ) = _seed_one_scope(
                connection,
                spec,
                canal_map,
                organization_map,
            )

            counters[
                f"scope_{action}"
            ] += 1

        details = {
            **counters,
            "scope_count": len(
                specs
            ),
            "whole_scope_count": sum(
                1
                for spec in specs
                if spec[
                    "range_mode"
                ]
                == RANGE_MODE_WHOLE
            ),
            "explicit_segment_scope_count": len(
                OFFICIAL_SEGMENT_SCOPE_SPECS
            ),
        }

        connection.execute(
            """
            INSERT INTO master_data_seed_history (
                seed_key,
                source_description,
                details_json
            )
            VALUES (?, ?, ?)
            """,
            (
                OFFICIAL_CANAL_MANAGEMENT_SCOPE_VERSION,
                OFFICIAL_CANAL_MANAGEMENT_SCOPE_SOURCE,
                json.dumps(
                    details,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            ),
        )

    return {
        "applied": True,
        "already_applied": False,
        "seed_key": (
            OFFICIAL_CANAL_MANAGEMENT_SCOPE_VERSION
        ),
        **details,
    }
