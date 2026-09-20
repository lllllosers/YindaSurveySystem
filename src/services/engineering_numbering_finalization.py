from __future__ import annotations

from dataclasses import dataclass

import database

from services.engineering_numbering import (
    _clean_text,
    _load_candidates,
    _prepare_plan,
)


ERROR = "error"
WARNING = "warning"
LINED_CHANNEL_FORM_CODE = "form_2_1"
LINED_CHANNEL_RECOMMENDED_MAX_LENGTH = 3000.0
STAKE_TOLERANCE = 0.001


@dataclass(frozen=True)
class EngineeringNumberingFinalizationIssue:
    severity: str
    code: str
    message: str
    engineering_asset_id: int | None = None
    canal_unit_id: int | None = None


@dataclass(frozen=True)
class EngineeringNumberingFinalizationPreview:
    project_id: int
    survey_batch_id: int
    total_assets: int
    group_count: int
    changed_code_count: int
    already_final_count: int
    provisional_count: int
    errors: tuple[EngineeringNumberingFinalizationIssue, ...]
    warnings: tuple[EngineeringNumberingFinalizationIssue, ...]

    @property
    def can_finalize(self):
        return not self.errors

    @property
    def has_warnings(self):
        return bool(self.warnings)

    def format_text(self):
        lines = [
            f"参与锁号工程：{self.total_assets}",
            f"编号分组：{self.group_count}",
            f"预计编号变化：{self.changed_code_count}",
            f"当前暂编：{self.provisional_count}",
            f"当前正式：{self.already_final_count}",
        ]

        if self.errors:
            lines.append("")
            lines.append("需要先处理：")
            for issue in self.errors:
                suffix = (
                    f"（记录ID：{issue.engineering_asset_id}）"
                    if issue.engineering_asset_id is not None
                    else ""
                )
                lines.append(
                    f"• {issue.message}{suffix}"
                )

        if self.warnings:
            lines.append("")
            lines.append("请确认以下情况：")
            for issue in self.warnings:
                suffix = (
                    f"（记录ID：{issue.engineering_asset_id}）"
                    if issue.engineering_asset_id is not None
                    else ""
                )
                lines.append(
                    f"• {issue.message}{suffix}"
                )

        if not self.errors and not self.warnings:
            lines.append("")
            lines.append(
                "未发现阻断问题或需要人工确认的连续性提示。"
            )

        return "\n".join(lines)


@dataclass(frozen=True)
class EngineeringNumberingFinalizationResult:
    project_id: int
    survey_batch_id: int
    total_assets: int
    group_count: int
    changed_code_count: int
    synchronized_record_count: int
    finalized_count: int
    warning_count: int


def _load_records(
    connection,
    *,
    project_id,
    survey_batch_id,
):
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT
                sr.id AS survey_record_id,
                sr.record_status,

                fd.form_code,

                ea.id AS engineering_asset_id,
                ea.engineering_asset_uid,
                ea.asset_name,
                ea.code_status,
                ea.canal_unit_id,

                ea.single_stake_text,
                ea.single_stake_value,
                ea.start_stake_text,
                ea.start_stake_value,
                ea.end_stake_text,
                ea.end_stake_value,

                canal.name AS canal_name

            FROM survey_records AS sr

            JOIN form_versions AS fv
              ON fv.id = sr.form_version_id

            JOIN form_definitions AS fd
              ON fd.id = fv.form_definition_id

            JOIN engineering_assets AS ea
              ON ea.id = sr.engineering_asset_id

            LEFT JOIN canal_units AS canal
              ON canal.id = ea.canal_unit_id

            WHERE sr.project_id = ?
              AND sr.survey_batch_id = ?
              AND sr.record_type = 'engineering'
              AND sr.record_status != 'void'
              AND ea.status != 'retired'

            ORDER BY
                ea.canal_unit_id,
                ea.start_stake_value,
                ea.single_stake_value,
                ea.id
            """,
            (
                project_id,
                survey_batch_id,
            ),
        ).fetchall()
    ]


def _issue(
    *,
    severity,
    code,
    message,
    row=None,
):
    return EngineeringNumberingFinalizationIssue(
        severity=severity,
        code=code,
        message=message,
        engineering_asset_id=(
            int(row["engineering_asset_id"])
            if (
                row is not None
                and row.get("engineering_asset_id") is not None
            )
            else None
        ),
        canal_unit_id=(
            int(row["canal_unit_id"])
            if (
                row is not None
                and row.get("canal_unit_id") is not None
            )
            else None
        ),
    )


def _audit_records(records):
    errors = []
    warnings = []

    for row in records:
        if _clean_text(row.get("record_status")) != "completed":
            errors.append(
                _issue(
                    severity=ERROR,
                    code="RECORD_NOT_COMPLETED",
                    message=(
                        "当前批次还有未完成（草稿）的工程调查记录。"
                        "请先完成调查，或删除确认无效的草稿记录，"
                        "再锁定正式编号。"
                    ),
                    row=row,
                )
            )

    lined_by_canal = {}

    for row in records:
        if _clean_text(row.get("form_code")) != LINED_CHANNEL_FORM_CODE:
            continue

        start_value = row.get("start_stake_value")
        end_value = row.get("end_stake_value")

        if start_value is None or end_value is None:
            errors.append(
                _issue(
                    severity=ERROR,
                    code="LINED_RANGE_INCOMPLETE",
                    message=(
                        "该防渗衬砌渠段缺少起点或终点桩号。"
                        "请补全起止桩号后再锁定正式编号。"
                    ),
                    row=row,
                )
            )
            continue

        start_value = float(start_value)
        end_value = float(end_value)

        if end_value <= start_value + STAKE_TOLERANCE:
            errors.append(
                _issue(
                    severity=ERROR,
                    code="LINED_RANGE_INVALID",
                    message=(
                        "该防渗衬砌渠段的终点桩号没有大于起点桩号。"
                        "请检查是否填反、填错或录入了零长度渠段，"
                        "修正后再锁号。"
                    ),
                    row=row,
                )
            )
            continue

        if (
            end_value - start_value
            > LINED_CHANNEL_RECOMMENDED_MAX_LENGTH
            + STAKE_TOLERANCE
        ):
            warnings.append(
                _issue(
                    severity=WARNING,
                    code="LINED_SECTION_OVER_3KM",
                    message=(
                        "该防渗衬砌渠段长度约 "
                        f"{(end_value - start_value) / 1000:.2f} km，"
                        "超过建议的 3 km 调查单元长度。"
                        "请确认是否需要进一步分段；"
                        "如现场边界和调查单元划分合理，可继续锁号。"
                    ),
                    row=row,
                )
            )

        canal_id = int(row["canal_unit_id"])

        lined_by_canal.setdefault(
            canal_id,
            [],
        ).append(
            {
                **row,
                "_start": start_value,
                "_end": end_value,
            }
        )

    for _, items in lined_by_canal.items():
        items.sort(
            key=lambda item: (
                item["_start"],
                item["_end"],
                _clean_text(
                    item.get("engineering_asset_uid")
                ),
                int(item["engineering_asset_id"]),
            )
        )

        previous = None
        covered_end = None

        for item in items:
            if previous is None:
                previous = item
                covered_end = item["_end"]
                continue

            start_value = item["_start"]
            end_value = item["_end"]

            assert covered_end is not None

            if start_value < covered_end - STAKE_TOLERANCE:
                errors.append(
                    _issue(
                        severity=ERROR,
                        code="LINED_SECTION_OVERLAP",
                        message=(
                            "检测到同一渠系中有两个防渗衬砌渠段范围重叠，"
                            "暂不能锁定正式编号。\n"
                            "前一渠段："
                            f"{previous.get('start_stake_text') or ''}"
                            " ～ "
                            f"{previous.get('end_stake_text') or ''}"
                            "\n后一渠段："
                            f"{item.get('start_stake_text') or ''}"
                            " ～ "
                            f"{item.get('end_stake_text') or ''}"
                            "\n请核对起止桩号，确认是否存在重复录入"
                            "或渠段边界填写错误。"
                        ),
                        row=item,
                    )
                )

            elif start_value > covered_end + STAKE_TOLERANCE:
                warnings.append(
                    _issue(
                        severity=WARNING,
                        code="LINED_SECTION_GAP",
                        message=(
                            "检测到同一渠系的两个防渗衬砌渠段之间存在"
                            f"约 {start_value - covered_end:.1f} m 的空档。\n"
                            "前一渠段结束："
                            f"{previous.get('end_stake_text') or ''}"
                            "\n后一渠段开始："
                            f"{item.get('start_stake_text') or ''}"
                            "\n如果该空档对应隧洞、渡槽、倒虹吸、"
                            "其他建筑物、未衬砌段或管理边界，"
                            "属于正常情况；确认没有漏录后可以继续锁号。"
                        ),
                        row=item,
                    )
                )

            if end_value > covered_end:
                covered_end = end_value
                previous = item

    return tuple(errors), tuple(warnings)


def _preview_with_connection(
    connection,
    *,
    project_id,
    survey_batch_id,
):
    rows = _load_candidates(
        connection,
        project_id=project_id,
        survey_batch_id=survey_batch_id,
    )

    assignments, numbering_issues = _prepare_plan(rows)

    records = _load_records(
        connection,
        project_id=project_id,
        survey_batch_id=survey_batch_id,
    )

    errors = [
        EngineeringNumberingFinalizationIssue(
            severity=ERROR,
            code=issue.code,
            message=issue.message,
            engineering_asset_id=issue.engineering_asset_id,
        )
        for issue in numbering_issues
    ]

    record_errors, warnings = _audit_records(records)
    errors.extend(record_errors)

    candidate_ids = {
        int(item["engineering_asset_id"])
        for item in assignments
    }

    for item in assignments:
        occupied = connection.execute(
            """
            SELECT
                id,
                asset_name
            FROM engineering_assets
            WHERE project_id = ?
              AND canal_unit_id = ?
              AND business_code = ?
              AND code_status = 'final'
              AND id != ?
            LIMIT 1
            """,
            (
                project_id,
                int(item["group_key"][0]),
                item["new_code"],
                int(item["engineering_asset_id"]),
            ),
        ).fetchone()

        if (
            occupied is not None
            and int(occupied["id"]) not in candidate_ids
        ):
            errors.append(
                EngineeringNumberingFinalizationIssue(
                    severity=ERROR,
                    code="FINAL_CODE_OCCUPIED_OUTSIDE_BATCH",
                    message=(
                        f"准备使用的正式编号 {item['new_code']} "
                        "已被同一渠系中的其他工程占用："
                        f"{occupied['asset_name'] or occupied['id']}。"
                        "请先核对该工程是否属于其他调查批次，"
                        "或是否存在重复工程记录。"
                    ),
                    engineering_asset_id=int(
                        item["engineering_asset_id"]
                    ),
                    canal_unit_id=int(item["group_key"][0]),
                )
            )

    return (
        rows,
        assignments,
        tuple(errors),
        tuple(warnings),
    )


def preview_engineering_numbering_finalization(
    *,
    project_id,
    survey_batch_id,
):
    if project_id is None:
        raise ValueError("项目不能为空。")

    if survey_batch_id is None:
        raise ValueError("当前调查批次不能为空。")

    project_id = int(project_id)
    survey_batch_id = int(survey_batch_id)

    with database.get_connection() as connection:
        (
            rows,
            assignments,
            errors,
            warnings,
        ) = _preview_with_connection(
            connection,
            project_id=project_id,
            survey_batch_id=survey_batch_id,
        )

    return EngineeringNumberingFinalizationPreview(
        project_id=project_id,
        survey_batch_id=survey_batch_id,
        total_assets=len(rows),
        group_count=len(
            {
                item["group_key"]
                for item in assignments
            }
        ),
        changed_code_count=sum(
            1
            for item in assignments
            if item["old_code"] != item["new_code"]
        ),
        already_final_count=sum(
            1
            for row in rows
            if _clean_text(row.get("code_status")) == "final"
        ),
        provisional_count=sum(
            1
            for row in rows
            if _clean_text(row.get("code_status")) != "final"
        ),
        errors=errors,
        warnings=warnings,
    )


def finalize_engineering_business_codes(
    *,
    project_id,
    survey_batch_id,
    accept_warnings=False,
):
    """
    重新核验、重新排序并正式锁号。

    编号变更属于派生编号状态，不增加 revision_no。
    """
    if project_id is None:
        raise ValueError("项目不能为空。")

    if survey_batch_id is None:
        raise ValueError("当前调查批次不能为空。")

    project_id = int(project_id)
    survey_batch_id = int(survey_batch_id)

    with database.get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")

        (
            rows,
            assignments,
            errors,
            warnings,
        ) = _preview_with_connection(
            connection,
            project_id=project_id,
            survey_batch_id=survey_batch_id,
        )

        if errors:
            preview = EngineeringNumberingFinalizationPreview(
                project_id=project_id,
                survey_batch_id=survey_batch_id,
                total_assets=len(rows),
                group_count=len(
                    {
                        item["group_key"]
                        for item in assignments
                    }
                ),
                changed_code_count=sum(
                    1
                    for item in assignments
                    if item["old_code"] != item["new_code"]
                ),
                already_final_count=sum(
                    1
                    for row in rows
                    if _clean_text(row.get("code_status")) == "final"
                ),
                provisional_count=sum(
                    1
                    for row in rows
                    if _clean_text(row.get("code_status")) != "final"
                ),
                errors=errors,
                warnings=warnings,
            )
            raise ValueError(
                "正式锁号预检未通过：\n"
                + preview.format_text()
            )

        if warnings and not accept_warnings:
            raise ValueError(
                "正式锁号存在需要人工核验的提示；"
                "请确认提示后再执行锁号。"
            )

        if not assignments:
            return EngineeringNumberingFinalizationResult(
                project_id=project_id,
                survey_batch_id=survey_batch_id,
                total_assets=0,
                group_count=0,
                changed_code_count=0,
                synchronized_record_count=0,
                finalized_count=0,
                warning_count=len(warnings),
            )

        asset_ids = [
            int(item["engineering_asset_id"])
            for item in assignments
        ]

        placeholders = ",".join(
            "?"
            for _ in asset_ids
        )

        # 先解除 final，避免交换/顺延编号时中间态
        # 触发具体渠道正式编号唯一索引。
        connection.execute(
            f"""
            UPDATE engineering_assets
            SET
                code_status = 'provisional',
                updated_at = datetime(
                    'now',
                    'localtime'
                )
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
                SET
                    business_code = ?,
                    updated_at = datetime(
                        'now',
                        'localtime'
                    )
                WHERE id = ?
                """,
                (
                    new_code,
                    asset_id,
                ),
            )

            cursor = connection.execute(
                """
                UPDATE survey_records
                SET
                    business_code = ?,
                    updated_at = datetime(
                        'now',
                        'localtime'
                    )
                WHERE engineering_asset_id = ?
                  AND survey_batch_id = ?
                  AND record_type = 'engineering'
                  AND record_status != 'void'
                """,
                (
                    new_code,
                    asset_id,
                    survey_batch_id,
                ),
            )

            if cursor.rowcount > 0:
                synchronized_record_count += int(
                    cursor.rowcount
                )

        # 所有业务编号都已经落到最终值后，
        # 再统一进入 final。
        connection.execute(
            f"""
            UPDATE engineering_assets
            SET
                code_status = 'final',
                updated_at = datetime(
                    'now',
                    'localtime'
                )
            WHERE id IN ({placeholders})
            """,
            asset_ids,
        )

        return EngineeringNumberingFinalizationResult(
            project_id=project_id,
            survey_batch_id=survey_batch_id,
            total_assets=len(assignments),
            group_count=len(
                {
                    item["group_key"]
                    for item in assignments
                }
            ),
            changed_code_count=changed_code_count,
            synchronized_record_count=(
                synchronized_record_count
            ),
            finalized_count=len(assignments),
            warning_count=len(warnings),
        )
