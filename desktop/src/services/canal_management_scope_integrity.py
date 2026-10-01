from __future__ import annotations

from dataclasses import dataclass

import database

from services.master_identity import (
    deterministic_master_uid,
)
from services.official_canal_management_scope import (
    OFFICIAL_CANAL_MANAGEMENT_SCOPE_VERSION,
    get_confirmed_official_scope_specs,
)


SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


@dataclass(
    frozen=True
)
class CanalManagementScopeIntegrityIssue:
    severity: str
    code: str
    message: str
    management_scope_id: (
        int
        | None
    ) = None


@dataclass(
    frozen=True
)
class CanalManagementScopeIntegrityReport:
    scope_count: int
    official_scope_count: int
    issues: tuple

    @property
    def error_count(
        self,
    ):
        return sum(
            1
            for issue in self.issues
            if issue.severity
            == SEVERITY_ERROR
        )

    @property
    def warning_count(
        self,
    ):
        return sum(
            1
            for issue in self.issues
            if issue.severity
            == SEVERITY_WARNING
        )

    @property
    def ok(
        self,
    ):
        return (
            self.error_count
            == 0
        )


def _issue(
    issues,
    severity,
    code,
    message,
    scope_id=None,
):
    issues.append(
        CanalManagementScopeIntegrityIssue(
            severity=severity,
            code=code,
            message=message,
            management_scope_id=(
                scope_id
            ),
        )
    )


def check_canal_management_scope_integrity():
    """
    检查当前渠道管理关系模型。

    CanalManagementScope 是渠道管理关系的唯一事实源。
    物理 CanalUnit 不参与管理归属一致性判断。
    """

    issues = []

    expected_specs = (
        get_confirmed_official_scope_specs()
    )

    with database.get_connection() as connection:
        seed_row = connection.execute(
            """
            SELECT seed_key
            FROM master_data_seed_history
            WHERE seed_key = ?
            """,
            (
                OFFICIAL_CANAL_MANAGEMENT_SCOPE_VERSION,
            ),
        ).fetchone()

        rows = [
            dict(
                row
            )
            for row in connection.execute(
                """
                SELECT
                    cms.*,
                    canal.name
                        AS canal_name,
                    canal.master_key
                        AS canal_master_key,
                    office.name
                        AS organization_name,
                    office.master_key
                        AS organization_master_key,
                    office.unit_type
                        AS organization_unit_type

                FROM canal_management_scopes
                    AS cms

                JOIN canal_units
                    AS canal
                    ON canal.id
                        = cms.canal_unit_id

                JOIN organization_units
                    AS office
                    ON office.id
                        = cms.organization_unit_id

                ORDER BY cms.id
                """
            ).fetchall()
        ]

        official_by_key = {
            row[
                "master_key"
            ]: row
            for row in rows
            if (
                row[
                    "master_key"
                ]
                is not None
                and str(
                    row[
                        "master_key"
                    ]
                ).strip()
            )
        }

    if seed_row is None:
        _issue(
            issues,
            SEVERITY_ERROR,
            "SCOPE_SEED_VERSION_MISSING",
            (
                "没有找到正式渠道管理范围"
                "主数据版本记录。"
            ),
        )

    for row in rows:
        scope_id = int(
            row[
                "id"
            ]
        )

        if (
            row[
                "organization_unit_type"
            ]
            != "water_office"
        ):
            _issue(
                issues,
                SEVERITY_ERROR,
                "SCOPE_ORGANIZATION_INVALID",
                (
                    f"渠道“{row['canal_name']}”"
                    "的管理范围没有关联"
                    "末级管理单位。"
                ),
                scope_id,
            )

        uid = str(
            row[
                "management_scope_uid"
            ]
            or ""
        ).strip()

        if not uid:
            _issue(
                issues,
                SEVERITY_ERROR,
                "SCOPE_UID_MISSING",
                (
                    f"渠道“{row['canal_name']}”"
                    "的管理范围缺少稳定 UID。"
                ),
                scope_id,
            )

        master_key = str(
            row[
                "master_key"
            ]
            or ""
        ).strip()

        if master_key:
            expected_uid = (
                deterministic_master_uid(
                    "canal_management_scope",
                    master_key,
                )
            )

            if uid != expected_uid:
                _issue(
                    issues,
                    SEVERITY_ERROR,
                    "SCOPE_UID_NOT_DETERMINISTIC",
                    (
                        "正式渠道管理范围"
                        "稳定 UID 与 master_key 不一致："
                        f"{master_key}。"
                    ),
                    scope_id,
                )

        mode = row[
            "range_mode"
        ]

        if mode == "segment_known":
            if (
                row[
                    "start_stake_value"
                ]
                is None
                or row[
                    "end_stake_value"
                ]
                is None
            ):
                _issue(
                    issues,
                    SEVERITY_ERROR,
                    "KNOWN_SEGMENT_BOUNDARY_MISSING",
                    (
                        f"渠道“{row['canal_name']}”"
                        "存在已知分段但缺少"
                        "起止桩号数值。"
                    ),
                    scope_id,
                )

        elif mode in (
            "whole",
            "segment_unknown",
        ):
            if any(
                row[
                    key
                ]
                is not None
                for key in (
                    "start_stake_text",
                    "start_stake_value",
                    "end_stake_text",
                    "end_stake_value",
                )
            ):
                _issue(
                    issues,
                    SEVERITY_ERROR,
                    "NON_KNOWN_SEGMENT_HAS_BOUNDARY",
                    (
                        f"渠道“{row['canal_name']}”"
                        "的范围类型不应携带"
                        "起止桩号。"
                    ),
                    scope_id,
                )

    for spec in expected_specs:
        master_key = (
            spec[
                "master_key"
            ]
        )

        row = official_by_key.get(
            master_key
        )

        if row is None:
            _issue(
                issues,
                SEVERITY_ERROR,
                "OFFICIAL_SCOPE_MISSING",
                (
                    "缺少已确认正式渠道管理范围："
                    f"{master_key}。"
                ),
            )
            continue

        if (
            row[
                "canal_master_key"
            ]
            != spec[
                "canal_master_key"
            ]
            or row[
                "organization_master_key"
            ]
            != spec[
                "organization_master_key"
            ]
            or row[
                "range_mode"
            ]
            != spec[
                "range_mode"
            ]
        ):
            _issue(
                issues,
                SEVERITY_ERROR,
                "OFFICIAL_SCOPE_MISMATCH",
                (
                    "正式渠道管理范围"
                    "与确认规格不一致："
                    f"{master_key}。"
                ),
                int(
                    row[
                        "id"
                    ]
                ),
            )

    return (
        CanalManagementScopeIntegrityReport(
            scope_count=len(
                rows
            ),
            official_scope_count=len(
                official_by_key
            ),
            issues=tuple(
                issues
            ),
        )
    )
