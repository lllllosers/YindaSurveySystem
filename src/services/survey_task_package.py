from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import database

from services.survey_task_lineage import (
    CURRENT_TASK_SCHEMA_VERSION,
    build_root_task_lineage,
)
from services.master_data_integrity import check_master_data_integrity
from services.survey_task_issue_history import (
    record_issued_survey_task,
)
from services.yd_package import (
    SURVEY_TASK_PACKAGE_KIND,
    encode_json_bytes,
    new_stable_token,
    normalize_task_package_path,
    write_package,
)
from version import APP_VERSION, APP_VERSION_LABEL


TASK_SCHEMA_VERSION = CURRENT_TASK_SCHEMA_VERSION


@dataclass(frozen=True)
class SurveyTaskExportRequest:
    project_id: int
    survey_batch_id: int
    organization_unit_id: int
    management_scope_uids: tuple[str, ...]
    task_name: str
    output_path: Path
    notes: str = ""


@dataclass(frozen=True)
class SurveyTaskExportResult:
    output_path: Path
    package_uid: str
    task_uid: str
    organization_name: str
    selected_management_scope_count: int
    reference_canal_count: int
    reference_organization_count: int
    form_count: int


def _clean_text(value):
    return str(value or "").strip()


def _require_stable_uid(row, field_name, entity_name):
    uid = _clean_text(row.get(field_name))
    if not uid:
        raise ValueError(f"{entity_name}缺少稳定 UID。")
    return uid


def _normalize_request(request):
    try:
        project_id = int(request.project_id)
        survey_batch_id = int(request.survey_batch_id)
        organization_unit_id = int(request.organization_unit_id)
    except (TypeError, ValueError) as error:
        raise ValueError("任务包项目、批次或管理单位 ID 无效。") from error

    scope_uids = []
    for raw_uid in request.management_scope_uids or ():
        uid = _clean_text(raw_uid)
        if not uid:
            raise ValueError("任务包包含无效分管范围 UID。")
        if uid not in scope_uids:
            scope_uids.append(uid)

    if not scope_uids:
        raise ValueError("调查任务至少需要选择一个分管范围。")

    task_name = _clean_text(request.task_name)
    if not task_name:
        raise ValueError("任务名称不能为空。")

    return {
        "project_id": project_id,
        "survey_batch_id": survey_batch_id,
        "organization_unit_id": organization_unit_id,
        "management_scope_uids": tuple(scope_uids),
        "task_name": task_name,
        "notes": _clean_text(request.notes),
        "output_path": normalize_task_package_path(request.output_path),
    }


def _load_context(normalized):
    with database.get_connection() as connection:
        project = connection.execute(
            """
            SELECT id, project_uid, name, short_name, status
            FROM projects
            WHERE id = ?
            """,
            (normalized["project_id"],),
        ).fetchone()
        if project is None:
            raise ValueError("没有找到指定项目。")

        batch = connection.execute(
            """
            SELECT id, survey_batch_uid, project_id, batch_name, batch_code,
                   start_date, end_date, status
            FROM survey_batches
            WHERE id = ?
            """,
            (normalized["survey_batch_id"],),
        ).fetchone()
        if batch is None:
            raise ValueError("没有找到指定调查批次。")
        if int(batch["project_id"]) != int(project["id"]):
            raise ValueError("调查批次不属于指定项目。")

        office = connection.execute(
            """
            SELECT id, organization_unit_uid, parent_id, name, unit_type,
                   business_code, status, description, sort_order
            FROM organization_units
            WHERE id = ?
            """,
            (normalized["organization_unit_id"],),
        ).fetchone()
        if office is None:
            raise ValueError("没有找到指定管理单位。")
        if office["unit_type"] != "water_office":
            raise ValueError("调查任务必须分配给末级管理单位。")
        if office["status"] != "active":
            raise ValueError("当前管理单位已停用，不能创建调查任务。")

        department = connection.execute(
            """
            SELECT id, organization_unit_uid, name, unit_type, business_code,
                   status, description, sort_order
            FROM organization_units
            WHERE id = ?
            """,
            (office["parent_id"],),
        ).fetchone()
        if department is None or department["unit_type"] != "department":
            raise ValueError("当前管理单位没有有效的所属基层处。")

        all_canals = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, canal_unit_uid, parent_id, name, canal_level,
                       status, description, sort_order
                FROM canal_units
                ORDER BY
                    CASE WHEN sort_order > 0 THEN sort_order ELSE 1000000 + id END,
                    id
                """
            ).fetchall()
        ]

        management_scopes = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    cms.id,
                    cms.management_scope_uid,
                    cms.canal_unit_id,
                    canal.canal_unit_uid,
                    canal.name AS canal_name,
                    canal.canal_level,
                    canal.status AS canal_status,
                    canal.sort_order AS canal_sort_order,
                    cms.organization_unit_id,
                    office.organization_unit_uid,
                    office.name AS organization_name,
                    cms.range_mode,
                    cms.start_stake_text,
                    cms.start_stake_value,
                    cms.end_stake_text,
                    cms.end_stake_value,
                    cms.sort_order,
                    cms.status,
                    cms.description
                FROM canal_management_scopes AS cms
                JOIN canal_units AS canal ON canal.id = cms.canal_unit_id
                JOIN organization_units AS office ON office.id = cms.organization_unit_id
                WHERE cms.organization_unit_id = ?
                  AND cms.status = 'active'
                ORDER BY
                    CASE
                        WHEN canal.sort_order > 0 THEN canal.sort_order
                        ELSE 1000000 + canal.id
                    END,
                    cms.sort_order,
                    cms.id
                """,
                (normalized["organization_unit_id"],),
            ).fetchall()
        ]

        forms = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    fd.form_code, fd.form_number, fd.form_name, fd.asset_type,
                    fd.sort_order, fv.version_code, fv.version_name,
                    fv.effective_date
                FROM form_definitions AS fd
                LEFT JOIN form_versions AS fv
                  ON fv.form_definition_id = fd.id
                 AND fv.is_current = 1
                WHERE fd.series = 'series_2'
                  AND fd.record_type = 'engineering'
                  AND fd.is_enabled = 1
                ORDER BY fd.sort_order, fd.form_code
                """
            ).fetchall()
        ]

    return {
        "project": dict(project),
        "batch": dict(batch),
        "office": dict(office),
        "department": dict(department),
        "all_canals": all_canals,
        "management_scopes": management_scopes,
        "forms": forms,
    }


def _build_selected_management_scopes(normalized, context):
    by_uid = {
        _clean_text(row["management_scope_uid"]): row
        for row in context["management_scopes"]
        if _clean_text(row["management_scope_uid"])
    }

    selected = []
    for uid in normalized["management_scope_uids"]:
        row = by_uid.get(uid)
        if row is None:
            raise ValueError(
                "所选分管范围不属于当前管理单位或已经停用："
                f"{uid}。"
            )
        if row["canal_status"] != "active":
            raise ValueError(f"任务不能包含停用渠系：{row['canal_name']}。")

        _require_stable_uid(row, "management_scope_uid", "渠道分管范围")
        _require_stable_uid(row, "canal_unit_uid", f"渠系“{row['canal_name']}”")
        _require_stable_uid(row, "organization_unit_uid", "管理单位")
        selected.append(row)

    return selected


def _collect_reference_canal_ids(selected_scopes, all_canals):
    by_id = {int(row["id"]): row for row in all_canals}
    reference_ids = set()

    for scope in selected_scopes:
        current = by_id.get(int(scope["canal_unit_id"]))
        if current is None:
            raise ValueError("分管范围对应渠系不存在。")

        visited = set()
        while current is not None:
            current_id = int(current["id"])
            if current_id in visited:
                raise ValueError("渠系层级存在循环引用。")
            visited.add(current_id)
            reference_ids.add(current_id)

            parent_id = current["parent_id"]
            if parent_id is None:
                break
            current = by_id.get(int(parent_id))
            if current is None:
                raise ValueError("渠系上级节点缺失。")

    return reference_ids


def _build_reference_organizations(context):
    department = context["department"]
    office = context["office"]
    department_uid = _require_stable_uid(
        department, "organization_unit_uid", "所属基层处"
    )
    office_uid = _require_stable_uid(
        office, "organization_unit_uid", "管理单位"
    )

    items = [
        {
            "organization_uid": department_uid,
            "parent_organization_uid": None,
            "name": department["name"],
            "unit_type": department["unit_type"],
            "business_code": department["business_code"],
            "status": department["status"],
            "description": department["description"],
            "sort_order": int(department["sort_order"] or 0),
        },
        {
            "organization_uid": office_uid,
            "parent_organization_uid": department_uid,
            "name": office["name"],
            "unit_type": office["unit_type"],
            "business_code": office["business_code"],
            "status": office["status"],
            "description": office["description"],
            "sort_order": int(office["sort_order"] or 0),
        },
    ]
    return items, department_uid, office_uid


def _build_reference_canals(context, reference_ids):
    by_id = {int(row["id"]): row for row in context["all_canals"]}
    items = []

    for row in context["all_canals"]:
        canal_id = int(row["id"])
        if canal_id not in reference_ids:
            continue

        canal_uid = _require_stable_uid(row, "canal_unit_uid", f"渠系“{row['name']}”")
        parent_uid = None
        if row["parent_id"] is not None:
            parent = by_id.get(int(row["parent_id"]))
            if parent is None:
                raise ValueError(f"渠系上级节点缺失：{row['name']}。")
            parent_uid = _require_stable_uid(
                parent, "canal_unit_uid", f"上级渠系“{parent['name']}”"
            )

        items.append(
            {
                "canal_uid": canal_uid,
                "parent_canal_uid": parent_uid,
                "name": row["name"],
                "canal_level": row["canal_level"],
                "status": row["status"],
                "description": row["description"],
                "sort_order": int(row["sort_order"] or 0),
            }
        )

    return items


def _build_management_scope_reference(selected_scopes):
    items = []
    for row in selected_scopes:
        items.append(
            {
                "management_scope_uid": _require_stable_uid(
                    row, "management_scope_uid", "渠道分管范围"
                ),
                "canal_uid": _require_stable_uid(
                    row, "canal_unit_uid", "渠道分管范围对应渠系"
                ),
                "organization_unit_uid": _require_stable_uid(
                    row, "organization_unit_uid", "渠道分管范围管理单位"
                ),
                "range_mode": row["range_mode"],
                "start_stake_text": row["start_stake_text"],
                "start_stake_value": row["start_stake_value"],
                "end_stake_text": row["end_stake_text"],
                "end_stake_value": row["end_stake_value"],
                "sort_order": int(row["sort_order"] or 0),
                "status": row["status"],
                "description": row["description"],
            }
        )
    return items


def _build_form_reference(context):
    return [
        {
            "form_code": row["form_code"],
            "form_number": row["form_number"],
            "form_name": row["form_name"],
            "asset_type": row["asset_type"],
            "version_code": row["version_code"],
            "version_name": row["version_name"],
            "effective_date": row["effective_date"],
        }
        for row in context["forms"]
    ]


def export_survey_task_package(request):
    """
    导出 Stage 14.4 新任务包。

    任务权限以 CanalManagementScope 为事实源；CanalUnit 仅作为物理渠道参考。
    """
    integrity = check_master_data_integrity()
    if not integrity.passed:
        raise ValueError("正式主数据一致性检查未通过，不能生成调查任务包。")

    normalized = _normalize_request(request)
    context = _load_context(normalized)

    project_uid = _require_stable_uid(context["project"], "project_uid", "项目")
    batch_uid = _require_stable_uid(
        context["batch"], "survey_batch_uid", "调查批次"
    )

    selected_scopes = _build_selected_management_scopes(normalized, context)
    reference_canal_ids = _collect_reference_canal_ids(
        selected_scopes, context["all_canals"]
    )
    organization_reference, department_uid, office_uid = (
        _build_reference_organizations(context)
    )
    canal_reference = _build_reference_canals(context, reference_canal_ids)
    scope_reference = _build_management_scope_reference(selected_scopes)
    form_reference = _build_form_reference(context)

    selected_scope_uids = [
        row["management_scope_uid"] for row in selected_scopes
    ]
    task_uid = new_stable_token()
    package_uid = new_stable_token()
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    lineage = build_root_task_lineage(
        task_uid
    )

    task_data = {
        "task_schema_version": TASK_SCHEMA_VERSION,
        "task_uid": task_uid,
        "lineage": lineage.as_dict(),
        "task_name": normalized["task_name"],
        "notes": normalized["notes"] or None,
        "project": {
            "project_uid": project_uid,
            "name": context["project"]["name"],
            "short_name": context["project"]["short_name"],
        },
        "survey_batch": {
            "survey_batch_uid": batch_uid,
            "batch_name": context["batch"]["batch_name"],
            "batch_code": context["batch"]["batch_code"],
            "start_date": context["batch"]["start_date"],
            "end_date": context["batch"]["end_date"],
        },
        "assignment": {
            "department_uid": department_uid,
            "department_name": context["department"]["name"],
            "organization_unit_uid": office_uid,
            "organization_name": context["office"]["name"],
        },
        "scope": {
            "selected_management_scope_uids": selected_scope_uids,
            "selected_management_scope_count": len(selected_scope_uids),
        },
        "created_at": created_at,
    }

    payload_files = {
        "task.json": encode_json_bytes(task_data),
        "reference/organization_units.json": encode_json_bytes(
            {"items": organization_reference}
        ),
        "reference/canal_units.json": encode_json_bytes(
            {"items": canal_reference}
        ),
        "reference/canal_management_scopes.json": encode_json_bytes(
            {"items": scope_reference}
        ),
        "reference/forms.json": encode_json_bytes({"items": form_reference}),
    }

    manifest = {
        "package_kind": SURVEY_TASK_PACKAGE_KIND,
        "task_schema_version": TASK_SCHEMA_VERSION,
        "created_at": created_at,
        "app_version": APP_VERSION,
        "app_version_label": APP_VERSION_LABEL,
        "task_uid": task_uid,
        "parent_task_uid": lineage.parent_task_uid,
        "root_task_uid": lineage.root_task_uid,
        "task_depth": lineage.depth,
        "project_uid": project_uid,
        "survey_batch_uid": batch_uid,
    }

    write_result = write_package(
        normalized["output_path"],
        package_uid=package_uid,
        manifest=manifest,
        payload_files=payload_files,
    )

    # 任务包成功落盘后，立即把“下发时事实”
    # 写入上级端不可变历史。
    # 权威历史直接复用本次写入包内的冻结文档，
    # 不重新读取 current CanalManagementScope。
    try:
        record_issued_survey_task(
            package_uid=package_uid,
            manifest=manifest,
            task_document=task_data,
            management_scopes=(
                scope_reference
            ),
            canal_units=(
                canal_reference
            ),
        )

    except Exception:
        # 没有权威下发历史的任务包不能流出。
        # write_package() 已保证目标文件原先不存在，
        # 因此这里可以安全删除本次刚生成的文件。
        try:
            write_result.output_path.unlink(
                missing_ok=True
            )
        except Exception as cleanup_error:
            raise RuntimeError(
                "调查任务包已经生成，但上级端下发历史"
                "保存失败，且未登记任务包无法自动删除："
                f"{write_result.output_path}。"
                "请勿分发该任务包。"
            ) from cleanup_error

        raise

    return SurveyTaskExportResult(
        output_path=write_result.output_path,
        package_uid=package_uid,
        task_uid=task_uid,
        organization_name=context["office"]["name"],
        selected_management_scope_count=len(selected_scope_uids),
        reference_canal_count=len(canal_reference),
        reference_organization_count=len(organization_reference),
        form_count=len(form_reference),
    )
