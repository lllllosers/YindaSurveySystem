from __future__ import annotations

from dataclasses import dataclass

import database
from services.official_master_data import (
    OFFICIAL_MASTER_DATA_VERSION,
)


SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


@dataclass(frozen=True)
class MasterDataIntegrityIssue:
    severity: str
    code: str
    message: str
    entity_type: str = ""
    entity_id: int | None = None


@dataclass(frozen=True)
class MasterDataIntegrityReport:
    organization_count: int
    department_count: int
    office_count: int
    canal_count: int
    canal_level_counts: dict[str, int]
    issues: tuple[MasterDataIntegrityIssue, ...]

    @property
    def error_count(self):
        return sum(
            1
            for issue in self.issues
            if issue.severity == SEVERITY_ERROR
        )

    @property
    def warning_count(self):
        return sum(
            1
            for issue in self.issues
            if issue.severity == SEVERITY_WARNING
        )

    @property
    def info_count(self):
        return sum(
            1
            for issue in self.issues
            if issue.severity == SEVERITY_INFO
        )

    @property
    def passed(self):
        return self.error_count == 0

    def format_text(self):
        lines = [
            "正式主数据一致性检查",
            "",
            (
                "组织机构："
                f"{self.organization_count} "
                f"（基层处 {self.department_count}，"
                f"管理单位 {self.office_count}）"
            ),
            (
                "渠系节点："
                f"{self.canal_count} "
                f"（01={self.canal_level_counts.get('01', 0)}，"
                f"02={self.canal_level_counts.get('02', 0)}，"
                f"03={self.canal_level_counts.get('03', 0)}，"
                f"04={self.canal_level_counts.get('04', 0)}）"
            ),
            (
                "检查结果："
                f"{self.error_count} 个错误，"
                f"{self.warning_count} 个警告，"
                f"{self.info_count} 个提示"
            ),
        ]

        if not self.issues:
            lines.extend(
                [
                    "",
                    "未发现问题。",
                ]
            )
            return "\n".join(lines)

        labels = {
            SEVERITY_ERROR: "错误",
            SEVERITY_WARNING: "警告",
            SEVERITY_INFO: "提示",
        }

        lines.append("")

        for issue in self.issues:
            lines.append(
                (
                    f"[{labels.get(issue.severity, issue.severity)}] "
                    f"{issue.code}：{issue.message}"
                )
            )

        return "\n".join(lines)


def _append_issue(
    issues,
    severity,
    code,
    message,
    *,
    entity_type="",
    entity_id=None,
):
    issues.append(
        MasterDataIntegrityIssue(
            severity=severity,
            code=code,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    )


def _detect_canal_cycles(
    canals_by_id,
    issues,
):
    for canal_id in canals_by_id:
        seen = set()
        current_id = canal_id

        while current_id is not None:
            if current_id in seen:
                _append_issue(
                    issues,
                    SEVERITY_ERROR,
                    "CANAL_CYCLE",
                    (
                        "渠系层级存在循环引用，"
                        f"涉及渠系 ID {current_id}。"
                    ),
                    entity_type="canal_unit",
                    entity_id=current_id,
                )
                break

            seen.add(current_id)

            current = canals_by_id.get(
                current_id
            )

            if current is None:
                break

            current_id = current[
                "parent_id"
            ]


def check_master_data_integrity():
    """
    检查 Stage 09 正式主数据是否满足后续任务范围和任务包使用条件。

    这里只检查已经确认的结构事实，不把尚未确认的业务规则硬编码进来。

    错误：
    - 官方种子版本不存在；
    - 组织/渠系官方节点数量或层级数量异常；
    - 稳定 UID 缺失；
    - 组织代码缺失/重复；
    - 管理单位父级无效；
    - 渠系父子层级无效或出现循环；
    - 正式排序值缺失或重复；
    - 同一父渠系下出现同层级同名重复节点。
    """

    issues = []

    with database.get_connection() as connection:
        seed_row = connection.execute(
            """
            SELECT seed_key
            FROM master_data_seed_history
            WHERE seed_key = ?
            """,
            (
                OFFICIAL_MASTER_DATA_VERSION,
            ),
        ).fetchone()

        organizations = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    id,
                    parent_id,
                    name,
                    unit_type,
                    business_code,
                    status,
                    organization_unit_uid,
                    master_key,
                    sort_order
                FROM organization_units
                WHERE master_key IS NOT NULL
                ORDER BY id
                """
            ).fetchall()
        ]

        canals = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    id,
                    parent_id,
                    name,
                    canal_level,
                    status,
                    canal_unit_uid,
                    master_key,
                    sort_order,
                    description
                FROM canal_units
                WHERE master_key IS NOT NULL
                ORDER BY id
                """
            ).fetchall()
        ]

    if seed_row is None:
        _append_issue(
            issues,
            SEVERITY_ERROR,
            "SEED_VERSION_MISSING",
            (
                "没有找到正式主数据种子版本 "
                f"{OFFICIAL_MASTER_DATA_VERSION}。"
            ),
        )

    departments = [
        item
        for item in organizations
        if item["unit_type"] == "department"
    ]

    offices = [
        item
        for item in organizations
        if item["unit_type"] == "water_office"
    ]

    if len(organizations) != 25:
        _append_issue(
            issues,
            SEVERITY_ERROR,
            "ORGANIZATION_COUNT",
            (
                "正式组织机构应为 25 个，"
                f"当前为 {len(organizations)} 个。"
            ),
        )

    if len(departments) != 5:
        _append_issue(
            issues,
            SEVERITY_ERROR,
            "DEPARTMENT_COUNT",
            (
                "正式基层处应为 5 个，"
                f"当前为 {len(departments)} 个。"
            ),
        )

    if len(offices) != 20:
        _append_issue(
            issues,
            SEVERITY_ERROR,
            "OFFICE_COUNT",
            (
                "正式末级管理单位应为 20 个，"
                f"当前为 {len(offices)} 个。"
            ),
        )

    organizations_by_id = {
        int(item["id"]): item
        for item in organizations
    }

    department_codes = {}

    for department in departments:
        department_id = int(
            department["id"]
        )

        uid = str(
            department[
                "organization_unit_uid"
            ]
            or ""
        ).strip()

        if not uid:
            _append_issue(
                issues,
                SEVERITY_ERROR,
                "ORGANIZATION_UID_MISSING",
                (
                    f"基层处“{department['name']}”"
                    "缺少稳定 UID。"
                ),
                entity_type="organization_unit",
                entity_id=department_id,
            )

        code = str(
            department["business_code"]
            or ""
        ).strip()

        if not code:
            _append_issue(
                issues,
                SEVERITY_ERROR,
                "DEPARTMENT_CODE_MISSING",
                (
                    f"基层处“{department['name']}”"
                    "缺少业务代码。"
                ),
                entity_type="organization_unit",
                entity_id=department_id,
            )
        elif code in department_codes:
            _append_issue(
                issues,
                SEVERITY_ERROR,
                "DEPARTMENT_CODE_DUPLICATE",
                (
                    "基层处业务代码重复："
                    f"{code}。"
                ),
                entity_type="organization_unit",
                entity_id=department_id,
            )
        else:
            department_codes[
                code
            ] = department_id

    office_codes_by_parent = {}

    for office in offices:
        office_id = int(
            office["id"]
        )

        uid = str(
            office[
                "organization_unit_uid"
            ]
            or ""
        ).strip()

        if not uid:
            _append_issue(
                issues,
                SEVERITY_ERROR,
                "ORGANIZATION_UID_MISSING",
                (
                    f"管理单位“{office['name']}”"
                    "缺少稳定 UID。"
                ),
                entity_type="organization_unit",
                entity_id=office_id,
            )

        parent_id = office[
            "parent_id"
        ]

        parent = (
            organizations_by_id.get(
                int(parent_id)
            )
            if parent_id is not None
            else None
        )

        if (
            parent is None
            or parent["unit_type"]
            != "department"
        ):
            _append_issue(
                issues,
                SEVERITY_ERROR,
                "OFFICE_PARENT_INVALID",
                (
                    f"管理单位“{office['name']}”"
                    "没有有效的所属基层处。"
                ),
                entity_type="organization_unit",
                entity_id=office_id,
            )

        code = str(
            office["business_code"]
            or ""
        ).strip()

        if not code:
            _append_issue(
                issues,
                SEVERITY_ERROR,
                "OFFICE_CODE_MISSING",
                (
                    f"管理单位“{office['name']}”"
                    "缺少业务代码。"
                ),
                entity_type="organization_unit",
                entity_id=office_id,
            )
        else:
            scope = int(
                parent_id
            ) if parent_id is not None else -1

            scope_codes = (
                office_codes_by_parent.setdefault(
                    scope,
                    {},
                )
            )

            if code in scope_codes:
                _append_issue(
                    issues,
                    SEVERITY_ERROR,
                    "OFFICE_CODE_DUPLICATE",
                    (
                        "同一基层处下管理单位"
                        f"业务代码重复：{code}。"
                    ),
                    entity_type="organization_unit",
                    entity_id=office_id,
                )
            else:
                scope_codes[
                    code
                ] = office_id

    organization_sort_orders = {}

    for organization in organizations:
        organization_id = int(
            organization["id"]
        )

        sort_order = int(
            organization[
                "sort_order"
            ]
            or 0
        )

        if sort_order <= 0:
            _append_issue(
                issues,
                SEVERITY_ERROR,
                "ORGANIZATION_SORT_MISSING",
                (
                    f"组织机构“{organization['name']}”"
                    "缺少正式排序值。"
                ),
                entity_type="organization_unit",
                entity_id=organization_id,
            )
        elif sort_order in organization_sort_orders:
            _append_issue(
                issues,
                SEVERITY_ERROR,
                "ORGANIZATION_SORT_DUPLICATE",
                (
                    "正式组织机构排序值重复："
                    f"{sort_order}。"
                ),
                entity_type="organization_unit",
                entity_id=organization_id,
            )
        else:
            organization_sort_orders[
                sort_order
            ] = organization_id

    level_counts = {
        level: 0
        for level in (
            "01",
            "02",
            "03",
            "04",
        )
    }

    for canal in canals:
        level = str(
            canal["canal_level"]
        )

        if level in level_counts:
            level_counts[level] += 1

    expected_level_counts = {
        "01": 3,
        "02": 2,
        "03": 47,
        "04": 16,
    }

    if len(canals) != 68:
        _append_issue(
            issues,
            SEVERITY_ERROR,
            "CANAL_COUNT",
            (
                "正式渠系节点应为 68 个，"
                f"当前为 {len(canals)} 个。"
            ),
        )

    for (
        level,
        expected_count,
    ) in (
        expected_level_counts.items()
    ):
        actual_count = (
            level_counts.get(
                level,
                0,
            )
        )

        if actual_count != expected_count:
            _append_issue(
                issues,
                SEVERITY_ERROR,
                "CANAL_LEVEL_COUNT",
                (
                    f"渠道级别 {level} 应为 "
                    f"{expected_count} 个，"
                    f"当前为 {actual_count} 个。"
                ),
            )

    canals_by_id = {
        int(item["id"]): item
        for item in canals
    }

    canal_sort_orders = {}
    sibling_keys = {}

    for canal in canals:
        canal_id = int(
            canal["id"]
        )

        uid = str(
            canal["canal_unit_uid"]
            or ""
        ).strip()

        if not uid:
            _append_issue(
                issues,
                SEVERITY_ERROR,
                "CANAL_UID_MISSING",
                (
                    f"渠系“{canal['name']}”"
                    "缺少稳定 UID。"
                ),
                entity_type="canal_unit",
                entity_id=canal_id,
            )

        sort_order = int(
            canal["sort_order"]
            or 0
        )

        if sort_order <= 0:
            _append_issue(
                issues,
                SEVERITY_ERROR,
                "CANAL_SORT_MISSING",
                (
                    f"渠系“{canal['name']}”"
                    "缺少正式排序值。"
                ),
                entity_type="canal_unit",
                entity_id=canal_id,
            )
        elif sort_order in canal_sort_orders:
            _append_issue(
                issues,
                SEVERITY_ERROR,
                "CANAL_SORT_DUPLICATE",
                (
                    "正式渠系排序值重复："
                    f"{sort_order}。"
                ),
                entity_type="canal_unit",
                entity_id=canal_id,
            )
        else:
            canal_sort_orders[
                sort_order
            ] = canal_id

        parent_id = canal[
            "parent_id"
        ]

        parent = (
            canals_by_id.get(
                int(parent_id)
            )
            if parent_id is not None
            else None
        )

        level = str(
            canal["canal_level"]
        )

        if (
            parent_id is not None
            and parent is None
        ):
            _append_issue(
                issues,
                SEVERITY_ERROR,
                "CANAL_PARENT_MISSING",
                (
                    f"渠系“{canal['name']}”"
                    "的上级渠系不存在于正式主数据。"
                ),
                entity_type="canal_unit",
                entity_id=canal_id,
            )

        if level == "04":
            if (
                parent is None
                or str(
                    parent["canal_level"]
                )
                != "03"
            ):
                _append_issue(
                    issues,
                    SEVERITY_ERROR,
                    "BRANCH_PARENT_INVALID",
                    (
                        f"分支渠“{canal['name']}”"
                        "必须挂在支渠节点下。"
                    ),
                    entity_type="canal_unit",
                    entity_id=canal_id,
                )

        elif level == "03":
            if (
                parent is None
                or str(
                    parent["canal_level"]
                )
                not in (
                    "01",
                    "02",
                )
            ):
                _append_issue(
                    issues,
                    SEVERITY_ERROR,
                    "LATERAL_PARENT_INVALID",
                    (
                        f"支渠“{canal['name']}”"
                        "必须挂在干渠或分干渠节点下。"
                    ),
                    entity_type="canal_unit",
                    entity_id=canal_id,
                )

        elif level in (
            "01",
            "02",
        ):
            if parent is not None:
                _append_issue(
                    issues,
                    SEVERITY_WARNING,
                    "TRUNK_PARENT_ASSIGNED",
                    (
                        f"骨干渠“{canal['name']}”"
                        "当前存在上级渠系。"
                    ),
                    entity_type="canal_unit",
                    entity_id=canal_id,
                )

        sibling_key = (
            int(parent_id)
            if parent_id is not None
            else None,
            level,
            str(
                canal["name"]
                or ""
            ).strip(),
        )

        if sibling_key in sibling_keys:
            _append_issue(
                issues,
                SEVERITY_ERROR,
                "CANAL_SIBLING_DUPLICATE",
                (
                    "同一上级渠系下出现"
                    "同层级同名渠道："
                    f"{canal['name']}。"
                ),
                entity_type="canal_unit",
                entity_id=canal_id,
            )
        else:
            sibling_keys[
                sibling_key
            ] = canal_id

    _detect_canal_cycles(
        canals_by_id,
        issues,
    )

    return MasterDataIntegrityReport(
        organization_count=(
            len(organizations)
        ),
        department_count=(
            len(departments)
        ),
        office_count=len(offices),
        canal_count=len(canals),
        canal_level_counts=(
            level_counts
        ),
        issues=tuple(issues),
    )
