from __future__ import annotations

from dataclasses import dataclass

import database

from forms.engineering.registry import get_engineering_form_definitions
from services.business_code import build_business_code


@dataclass(frozen=True)
class EngineeringNumberingIssue:
    code: str
    message: str
    engineering_asset_id: int | None = None


@dataclass(frozen=True)
class EngineeringNumberingPreview:
    project_id: int
    survey_batch_id: int
    total_assets: int
    group_count: int
    changed_code_count: int
    final_to_provisional_count: int
    issues: tuple[EngineeringNumberingIssue, ...]

    @property
    def can_apply(self):
        return not self.issues

    def format_text(self):
        lines = [
            f"参与整理工程：{self.total_assets}",
            f"编号分组：{self.group_count}",
            f"预计编号变化：{self.changed_code_count}",
            f"正式 → 暂编：{self.final_to_provisional_count}",
        ]
        if not self.issues:
            lines.append("未发现阻断性编号问题。")
        else:
            lines.append("")
            lines.append("阻断问题：")
            for issue in self.issues:
                suffix = (
                    f" [工程ID {issue.engineering_asset_id}]"
                    if issue.engineering_asset_id is not None
                    else ""
                )
                lines.append(f"- {issue.code}：{issue.message}{suffix}")
        return "\n".join(lines)


    def format_user_text(self):
        lines = [
            f"参与整理工程：{self.total_assets}",
            f"编号分组：{self.group_count}",
            f"预计编号变化：{self.changed_code_count}",
            f"正式编号转回暂编：{self.final_to_provisional_count}",
        ]
        if not self.issues:
            lines.append("未发现需要先处理的编号问题。")
        else:
            lines.append("")
            lines.append("请先处理以下问题：")
            lines.extend(f"• {issue.message}" for issue in self.issues)
        return "\n".join(lines)

@dataclass(frozen=True)
class EngineeringNumberingResult:
    project_id: int
    survey_batch_id: int
    total_assets: int
    group_count: int
    changed_code_count: int
    synchronized_record_count: int
    final_to_provisional_count: int


def _clean_text(value):
    return str(value or "").strip()


def _load_candidates(connection, *, project_id, survey_batch_id):
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT DISTINCT
                ea.id AS engineering_asset_id,
                ea.engineering_asset_uid,
                ea.asset_name,
                ea.asset_type,
                ea.business_code,
                ea.code_status,
                ea.single_stake_text,
                ea.single_stake_value,
                ea.start_stake_text,
                ea.start_stake_value,
                ea.end_stake_text,
                ea.end_stake_value,
                ea.organization_unit_id,
                office.business_code AS office_business_code,
                office.name AS office_name,
                department.business_code AS department_business_code,
                department.name AS department_name,
                ea.canal_unit_id,
                canal.canal_unit_uid,
                canal.name AS canal_name,
                canal.canal_level
            FROM engineering_assets AS ea
            JOIN survey_records AS sr
              ON sr.engineering_asset_id = ea.id
            LEFT JOIN organization_units AS office
              ON office.id = ea.organization_unit_id
            LEFT JOIN organization_units AS department
              ON department.id = office.parent_id
            LEFT JOIN canal_units AS canal
              ON canal.id = ea.canal_unit_id
            WHERE ea.project_id = ?
              AND sr.survey_batch_id = ?
              AND sr.record_type = 'engineering'
              AND sr.record_status != 'void'
              AND ea.status != 'retired'
            ORDER BY ea.canal_unit_id, ea.id
            """,
            (project_id, survey_batch_id),
        ).fetchall()
    ]


def _definition_by_asset_type():
    return {
        definition.asset_type: definition
        for definition in get_engineering_form_definitions()
    }


def _prepare_plan(rows):
    definitions = _definition_by_asset_type()
    issues = []
    grouped = {}

    for row in rows:
        asset_id = int(row["engineering_asset_id"])
        definition = definitions.get(_clean_text(row.get("asset_type")))
        if definition is None:
            issues.append(
                EngineeringNumberingIssue(
                    code="ASSET_TYPE_UNSUPPORTED",
                    message="工程类型未注册，无法确定正式工程类型代码。",
                    engineering_asset_id=asset_id,
                )
            )
            continue

        department_code = _clean_text(row.get("department_business_code"))
        office_code = _clean_text(row.get("office_business_code"))
        canal_level = _clean_text(row.get("canal_level"))
        engineering_type_code = _clean_text(definition.business_type_code)

        if not department_code:
            issues.append(
                EngineeringNumberingIssue(
                    code="DEPARTMENT_CODE_MISSING",
                    message="工程所属基层处缺少业务代码。",
                    engineering_asset_id=asset_id,
                )
            )
            continue
        if not office_code:
            issues.append(
                EngineeringNumberingIssue(
                    code="OFFICE_CODE_MISSING",
                    message="工程所属水管所缺少业务代码。",
                    engineering_asset_id=asset_id,
                )
            )
            continue
        if not canal_level:
            issues.append(
                EngineeringNumberingIssue(
                    code="CANAL_LEVEL_MISSING",
                    message="工程所属具体渠系缺少渠道层级。",
                    engineering_asset_id=asset_id,
                )
            )
            continue

        single_value = row.get("single_stake_value")
        start_value = row.get("start_stake_value")
        end_value = row.get("end_stake_value")

        if single_value is not None:
            position = float(single_value)
            secondary = position
        elif start_value is not None:
            position = float(start_value)
            secondary = float(end_value) if end_value is not None else position
            if end_value is not None and float(end_value) <= float(start_value):
                issues.append(
                    EngineeringNumberingIssue(
                        code="RANGE_STAKE_REVERSED",
                        message="区间工程终点桩号小于起点桩号，不能参与排序。",
                        engineering_asset_id=asset_id,
                    )
                )
                continue
        else:
            issues.append(
                EngineeringNumberingIssue(
                    code="STAKE_MISSING",
                    message="工程缺少可用于上游→下游排序的单点桩号或起点桩号。",
                    engineering_asset_id=asset_id,
                )
            )
            continue

        try:
            build_business_code(
                department_code=department_code,
                water_office_code=office_code,
                canal_level_code=canal_level,
                engineering_type_code=engineering_type_code,
                sequence=1,
            )
        except ValueError as error:
            issues.append(
                EngineeringNumberingIssue(
                    code="BUSINESS_PREFIX_INVALID",
                    message=str(error),
                    engineering_asset_id=asset_id,
                )
            )
            continue

        group_key = (
            int(row["canal_unit_id"]),
            department_code,
            office_code,
            canal_level,
            engineering_type_code,
        )
        grouped.setdefault(group_key, []).append(
            {
                **row,
                "_position": position,
                "_secondary": secondary,
                "_department_code": department_code,
                "_office_code": office_code,
                "_canal_level": canal_level,
                "_engineering_type_code": engineering_type_code,
            }
        )

    assignments = []
    for group_key, items in grouped.items():
        items.sort(
            key=lambda item: (
                float(item["_position"]),
                float(item["_secondary"]),
                _clean_text(item.get("engineering_asset_uid")),
                int(item["engineering_asset_id"]),
            )
        )
        if len(items) > 999:
            issues.append(
                EngineeringNumberingIssue(
                    code="SEQUENCE_OVERFLOW",
                    message="同一具体渠道、同一工程类型超过999个工程，三位顺序号无法容纳。",
                )
            )
            continue

        for sequence, item in enumerate(items, start=1):
            new_code = build_business_code(
                department_code=item["_department_code"],
                water_office_code=item["_office_code"],
                canal_level_code=item["_canal_level"],
                engineering_type_code=item["_engineering_type_code"],
                sequence=sequence,
            )
            assignments.append(
                {
                    "engineering_asset_id": int(item["engineering_asset_id"]),
                    "old_code": _clean_text(item.get("business_code")),
                    "new_code": new_code,
                    "old_code_status": _clean_text(item.get("code_status")) or "provisional",
                    "group_key": group_key,
                }
            )

    return assignments, tuple(issues)


def preview_engineering_business_code_renumber(*, project_id, survey_batch_id):
    if project_id is None:
        raise ValueError("项目不能为空。")
    if survey_batch_id is None:
        raise ValueError("当前调查批次不能为空。")

    with database.get_connection() as connection:
        rows = _load_candidates(
            connection,
            project_id=int(project_id),
            survey_batch_id=int(survey_batch_id),
        )

    assignments, issues = _prepare_plan(rows)
    return EngineeringNumberingPreview(
        project_id=int(project_id),
        survey_batch_id=int(survey_batch_id),
        total_assets=len(rows),
        group_count=len({item["group_key"] for item in assignments}),
        changed_code_count=sum(
            1 for item in assignments if item["old_code"] != item["new_code"]
        ),
        final_to_provisional_count=sum(
            1 for item in assignments if item["old_code_status"] == "final"
        ),
        issues=issues,
    )


def renumber_engineering_business_codes(*, project_id, survey_batch_id):
    """
    当前批次可重复执行的业务编号整理：
    具体渠系 + 正式编号前四段分组，按桩号上游→下游排序。
    只改编号与编号状态，不修改 revision_no/source_revision_no。
    """
    if project_id is None:
        raise ValueError("项目不能为空。")
    if survey_batch_id is None:
        raise ValueError("当前调查批次不能为空。")

    project_id = int(project_id)
    survey_batch_id = int(survey_batch_id)

    with database.get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        rows = _load_candidates(
            connection,
            project_id=project_id,
            survey_batch_id=survey_batch_id,
        )
        assignments, issues = _prepare_plan(rows)

        if issues:
            details = "\n".join(
                (
                    f"{item.code}：{item.message}"
                    + (
                        f" [工程ID {item.engineering_asset_id}]"
                        if item.engineering_asset_id is not None
                        else ""
                    )
                )
                for item in issues[:10]
            )
            raise ValueError("业务编号整理预检未通过：\n" + details)

        if not assignments:
            return EngineeringNumberingResult(
                project_id=project_id,
                survey_batch_id=survey_batch_id,
                total_assets=0,
                group_count=0,
                changed_code_count=0,
                synchronized_record_count=0,
                final_to_provisional_count=0,
            )

        asset_ids = [item["engineering_asset_id"] for item in assignments]
        placeholders = ",".join("?" for _ in asset_ids)

        # 先解除 final 状态，避免旧正式唯一索引在交换/顺延编号的中间态冲突。
        connection.execute(
            f"""
            UPDATE engineering_assets
            SET code_status = 'provisional',
                updated_at = datetime('now', 'localtime')
            WHERE id IN ({placeholders})
            """,
            asset_ids,
        )

        changed_code_count = 0
        synchronized_record_count = 0

        for item in assignments:
            asset_id = int(item["engineering_asset_id"])
            new_code = item["new_code"]
            if item["old_code"] != new_code:
                changed_code_count += 1

            connection.execute(
                """
                UPDATE engineering_assets
                SET business_code = ?,
                    code_status = 'provisional',
                    updated_at = datetime('now', 'localtime')
                WHERE id = ?
                """,
                (new_code, asset_id),
            )

            cursor = connection.execute(
                """
                UPDATE survey_records
                SET business_code = ?,
                    updated_at = datetime('now', 'localtime')
                WHERE engineering_asset_id = ?
                  AND survey_batch_id = ?
                  AND record_type = 'engineering'
                  AND record_status != 'void'
                """,
                (new_code, asset_id, survey_batch_id),
            )
            if cursor.rowcount > 0:
                synchronized_record_count += int(cursor.rowcount)

        return EngineeringNumberingResult(
            project_id=project_id,
            survey_batch_id=survey_batch_id,
            total_assets=len(assignments),
            group_count=len({item["group_key"] for item in assignments}),
            changed_code_count=changed_code_count,
            synchronized_record_count=synchronized_record_count,
            final_to_provisional_count=sum(
                1 for item in assignments if item["old_code_status"] == "final"
            ),
        )
