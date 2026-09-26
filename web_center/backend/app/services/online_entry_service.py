from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import sys
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.central_record import CentralEngineeringAsset, CentralInspectionResult, CentralSurveyRecord
from app.models.online_entry import OnlineSurveyEntry
from app.models.project import Project, SurveyBatch
from app.models.survey_task import SurveyTask
from app.schemas.online_entry import OnlineEntryPayload, OnlineEntryUpdate
from app.services.master_data_service import REPOSITORY_ROOT


DESKTOP_SRC = Path(REPOSITORY_ROOT) / "src"
if str(DESKTOP_SRC) not in sys.path:
    sys.path.insert(0, str(DESKTOP_SRC))

from forms.engineering.registry import (  # noqa: E402
    get_engineering_form_definition,
    get_engineering_form_definitions,
)


class OnlineEntryStateError(ValueError):
    pass


def form_definitions() -> list[dict]:
    result = []
    for definition in get_engineering_form_definitions():
        result.append({
            "form_code": definition.form_code,
            "form_number": definition.form_number,
            "form_name": definition.form_name,
            "asset_type": definition.asset_type,
            "asset_name_field": definition.asset_name_field,
            "fields": [
                {
                    "key": field.key,
                    "label": field.label,
                    "display_label": field.display_label,
                    "input_type": field.input_type,
                    "required": field.required,
                    "unit": field.unit,
                    "placeholder": field.placeholder,
                    "maximum": field.maximum,
                    "choices": list(field.choices or ()),
                }
                for field in definition.fields
            ],
            "sections": [
                {
                    "title": section.title,
                    "rows": [
                        {
                            "field_keys": list(row.field_keys),
                            "label": row.label,
                            "separator": row.separator,
                        }
                        for row in section.rows
                    ],
                }
                for section in definition.sections
            ],
            "evaluation_items": [dict(item) for item in definition.evaluation_items],
            "grade_options": list(definition.grade_options),
            "evaluation_title": definition.evaluation_title,
            "evaluation_note": definition.evaluation_note,
            "conclusion_title": definition.conclusion_title,
        })
    return result


def _task_context(db: Session, task_uid: str, scope_uid: str, form_code: str):
    result = db.execute(
        select(SurveyTask, Project, SurveyBatch)
        .join(Project, Project.id == SurveyTask.project_id)
        .join(SurveyBatch, SurveyBatch.id == SurveyTask.survey_batch_id)
        .where(SurveyTask.task_uid == task_uid)
    ).one_or_none()
    if result is None:
        raise ValueError("所选调查任务不存在。")
    task, project, batch = result
    if task.status in {"cancelled", "closed"}:
        raise ValueError("该调查任务已结束，不能继续录入。")
    frozen = task.frozen_snapshot_json if isinstance(task.frozen_snapshot_json, dict) else {}
    scopes = frozen.get("management_scopes") if isinstance(frozen.get("management_scopes"), list) else []
    scope = next((item for item in scopes if item.get("management_scope_uid") == scope_uid), None)
    if scope is None:
        raise ValueError("所选调查范围不属于该任务。")
    allowed_forms = {
        str(item.get("form_code"))
        for item in frozen.get("forms", [])
        if isinstance(item, dict)
    }
    definition = get_engineering_form_definition(form_code)
    if definition is None or form_code not in allowed_forms:
        raise ValueError("所选调查表不属于该任务。")
    return task, project, batch, scope, definition


def _asset_name(definition, form_data: dict) -> str | None:
    value = form_data.get(definition.asset_name_field)
    text = str(value).strip() if value is not None else ""
    return text[:300] or None


def create_entry(db: Session, payload: OnlineEntryPayload, creator: User) -> OnlineSurveyEntry:
    task, project, batch, scope, definition = _task_context(
        db, payload.task_uid, payload.management_scope_uid, payload.form_code
    )
    row = OnlineSurveyEntry(
        task_uid=task.task_uid,
        project_uid=project.project_uid,
        survey_batch_uid=batch.survey_batch_uid,
        management_scope_uid=str(scope["management_scope_uid"]),
        organization_unit_uid=str(scope["organization_unit_uid"]),
        organization_name=str(scope.get("organization_name") or task.organization_name),
        canal_unit_uid=str(scope["canal_uid"]),
        canal_name=str(scope.get("canal_name") or ""),
        form_code=definition.form_code,
        form_name=definition.form_name,
        asset_name=_asset_name(definition, payload.form_data),
        form_data_json=payload.form_data,
        evaluations_json=payload.evaluations,
        conclusion_json=payload.conclusion,
        created_by_user_uid=creator.user_uid,
        created_by_username=creator.username,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_entry(db: Session, row: OnlineSurveyEntry, payload: OnlineEntryUpdate) -> OnlineSurveyEntry:
    if row.status not in {"draft", "rejected"}:
        raise OnlineEntryStateError("该记录已经提交，不能再修改。")
    definition = get_engineering_form_definition(row.form_code)
    if definition is None:
        raise RuntimeError("调查表定义不存在。")
    row.form_data_json = payload.form_data
    row.evaluations_json = payload.evaluations
    row.conclusion_json = payload.conclusion
    row.asset_name = _asset_name(definition, payload.form_data)
    row.status = "draft"
    row.review_notes = None
    row.revision_no += 1
    db.commit()
    db.refresh(row)
    return row


def validate_for_submit(row: OnlineSurveyEntry) -> list[str]:
    definition = get_engineering_form_definition(row.form_code)
    if definition is None:
        return ["调查表定义不存在"]
    data = row.form_data_json if isinstance(row.form_data_json, dict) else {}
    errors = []
    for field in definition.fields:
        value = data.get(field.key)
        if field.required and (value is None or str(value).strip() == ""):
            errors.append(f"请填写“{field.display_label}”")
            continue
        if value is None or str(value).strip() == "":
            continue
        if field.input_type == "choice" and str(value) not in (field.choices or ()):
            errors.append(f"“{field.display_label}”的选项无效")
        elif field.input_type == "month":
            try:
                datetime.strptime(str(value), "%Y-%m")
            except ValueError:
                errors.append(f"“{field.display_label}”的月份无效")
        elif field.input_type in {"decimal", "signed_decimal", "integer"}:
            try:
                number = Decimal(str(value))
                if field.input_type == "integer" and number != number.to_integral_value():
                    errors.append(f"“{field.display_label}”应填写整数")
                if field.maximum is not None and number > field.maximum:
                    errors.append(f"“{field.display_label}”不能大于{field.maximum}")
            except InvalidOperation:
                errors.append(f"“{field.display_label}”应填写数字")
    evaluations = row.evaluations_json if isinstance(row.evaluations_json, list) else []
    grade_by_code = {
        str(item.get("item_code")): str(item.get("grade") or "")
        for item in evaluations if isinstance(item, dict)
    }
    for item in definition.evaluation_items:
        if grade_by_code.get(str(item["item_code"])) not in definition.grade_options:
            errors.append(f"请完成“{item['item_name']}”的评价")
    conclusion = row.conclusion_json if isinstance(row.conclusion_json, dict) else {}
    if not str(conclusion.get("survey_date") or "").strip():
        errors.append("请选择调查日期")
    if str(conclusion.get("overall_grade") or "") not in definition.grade_options:
        errors.append("请选择总体评价")
    if not str(conclusion.get("surveyor_signatures") or "").strip():
        errors.append("请填写调查人员")
    if not str(conclusion.get("survey_comment") or "").strip():
        errors.append("请填写调查意见与建议")
    return errors


def submit_entry(db: Session, row: OnlineSurveyEntry) -> OnlineSurveyEntry:
    if row.status not in {"draft", "rejected"}:
        raise OnlineEntryStateError("只有草稿或退回记录可以提交。")
    errors = validate_for_submit(row)
    if errors:
        raise ValueError("；".join(errors[:8]))
    row.status = "submitted"
    row.submitted_at = datetime.now().astimezone()
    row.review_notes = None
    db.commit()
    db.refresh(row)
    return row


def list_entries(
    db: Session, *, status: str | None, task_uid: str | None, creator_uid: str | None,
    limit: int, offset: int,
) -> tuple[list[tuple[OnlineSurveyEntry, SurveyTask, Project, SurveyBatch]], int]:
    base = (
        select(OnlineSurveyEntry, SurveyTask, Project, SurveyBatch)
        .select_from(OnlineSurveyEntry)
        .join(SurveyTask, SurveyTask.task_uid == OnlineSurveyEntry.task_uid)
        .join(Project, Project.project_uid == OnlineSurveyEntry.project_uid)
        .join(SurveyBatch, SurveyBatch.survey_batch_uid == OnlineSurveyEntry.survey_batch_uid)
    )
    count_stmt = select(func.count()).select_from(OnlineSurveyEntry)
    for condition in (
        OnlineSurveyEntry.status == status if status else None,
        OnlineSurveyEntry.task_uid == task_uid if task_uid else None,
        OnlineSurveyEntry.created_by_user_uid == creator_uid if creator_uid else None,
    ):
        if condition is not None:
            base = base.where(condition)
            count_stmt = count_stmt.where(condition)
    rows = db.execute(
        base.order_by(OnlineSurveyEntry.updated_at.desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), int(db.scalar(count_stmt) or 0)


def get_entry(db: Session, entry_uid: str) -> OnlineSurveyEntry | None:
    return db.scalar(select(OnlineSurveyEntry).where(OnlineSurveyEntry.entry_uid == entry_uid))


def _hash(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def accept_and_import(db: Session, row: OnlineSurveyEntry, reviewer: User, notes: str | None) -> None:
    if row.status != "submitted":
        raise OnlineEntryStateError("只有待审核记录可以审核。")
    definition = get_engineering_form_definition(row.form_code)
    if definition is None:
        raise RuntimeError("调查表定义不存在。")
    now = datetime.now().astimezone()
    asset_uid = uuid5(NAMESPACE_URL, f"yinda:web-entry:asset:{row.entry_uid}").hex
    record_uid = uuid5(NAMESPACE_URL, f"yinda:web-entry:record:{row.entry_uid}").hex
    business_code = f"WEB-{now:%Y%m%d}-{row.entry_uid[:8].upper()}"
    asset_payload = {
        "engineering_asset_uid": asset_uid,
        "project_uid": row.project_uid,
        "asset_name": row.asset_name,
        "asset_type": definition.asset_type,
        "organization_unit_uid": row.organization_unit_uid,
        "canal_unit_uid": row.canal_unit_uid,
        "business_code": business_code,
        "first_survey_batch_uid": row.survey_batch_uid,
        "status": "active",
        "notes": "Web端在线补录",
        "created_at": row.created_at.isoformat(),
        "updated_at": now.isoformat(),
        "revision_no": row.revision_no,
    }
    conclusion = row.conclusion_json if isinstance(row.conclusion_json, dict) else {}
    record_payload = {
        "survey_record_uid": record_uid,
        "source_task_uid": row.task_uid,
        "source_management_scope_uid": row.management_scope_uid,
        "project_uid": row.project_uid,
        "survey_batch_uid": row.survey_batch_uid,
        "form": {
            "form_code": definition.form_code,
            "form_number": definition.form_number,
            "form_name": definition.form_name,
            "asset_type": definition.asset_type,
            "version_code": "WEB-1",
            "version_name": "Web端在线录入版",
        },
        "record_type": "engineering",
        "organization_unit_uid": row.organization_unit_uid,
        "canal_unit_uid": row.canal_unit_uid,
        "engineering_asset_uid": asset_uid,
        "business_code": business_code,
        "survey_date": conclusion.get("survey_date"),
        "overall_grade": conclusion.get("overall_grade"),
        "survey_comment": conclusion.get("survey_comment"),
        "surveyor_signatures": conclusion.get("surveyor_signatures"),
        "water_office_manager_signature": conclusion.get("water_office_manager_signature"),
        "engineering_section_chief_signature": conclusion.get("engineering_section_chief_signature"),
        "department_head_signature": conclusion.get("department_head_signature"),
        "record_status": "completed",
        "record_data": row.form_data_json,
        "source_channel": "web_online_entry",
        "created_at": row.created_at.isoformat(),
        "updated_at": now.isoformat(),
        "revision_no": row.revision_no,
    }
    asset = CentralEngineeringAsset(
        engineering_asset_uid=asset_uid, project_uid=row.project_uid,
        asset_name=row.asset_name, asset_type=definition.asset_type,
        organization_unit_uid=row.organization_unit_uid, canal_unit_uid=row.canal_unit_uid,
        business_code=business_code, revision_no=row.revision_no,
        content_sha256=_hash(asset_payload), payload_json=asset_payload,
        current_submission_uid=row.entry_uid,
    )
    record = CentralSurveyRecord(
        survey_record_uid=record_uid, engineering_asset_uid=asset_uid,
        project_uid=row.project_uid, survey_batch_uid=row.survey_batch_uid,
        form_code=row.form_code, organization_unit_uid=row.organization_unit_uid,
        canal_unit_uid=row.canal_unit_uid, source_task_uid=row.task_uid,
        source_management_scope_uid=row.management_scope_uid, record_status="completed",
        revision_no=row.revision_no, content_sha256=_hash(record_payload),
        payload_json=record_payload, current_submission_uid=row.entry_uid, imported_at=now,
    )
    db.add_all([asset, record])
    for item in row.evaluations_json:
        payload = {
            "survey_record_uid": record_uid,
            "item_code": item.get("item_code"),
            "category": item.get("category"),
            "item_name": item.get("item_name"),
            "grade": item.get("grade"),
            "description": item.get("description"),
            "remark": item.get("remark"),
            "updated_at": now.isoformat(),
        }
        db.add(CentralInspectionResult(
            survey_record_uid=record_uid,
            item_code=str(item.get("item_code")),
            payload_json=payload,
            current_submission_uid=row.entry_uid,
        ))
    row.status = "imported"
    row.review_notes = notes
    row.reviewed_by_user_uid = reviewer.user_uid
    row.reviewed_by_username = reviewer.username
    row.reviewed_at = now
    row.imported_at = now
    db.commit()


def reject_entry(db: Session, row: OnlineSurveyEntry, reviewer: User, notes: str) -> None:
    if row.status != "submitted":
        raise OnlineEntryStateError("只有待审核记录可以审核。")
    row.status = "rejected"
    row.review_notes = notes
    row.reviewed_by_user_uid = reviewer.user_uid
    row.reviewed_by_username = reviewer.username
    row.reviewed_at = datetime.now().astimezone()
    db.commit()
