from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sys

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.central_record import (
    CentralEngineeringAsset,
    CentralInspectionResult,
    CentralSurveyMedia,
    CentralSurveyRecord,
)
from app.models.result_submission import ResultSubmission
from app.models.online_entry import OnlineSurveyEntry
from app.models.survey_task import SurveyTask
from app.services.master_data_service import REPOSITORY_ROOT


DESKTOP_SRC = REPOSITORY_ROOT / "src"


@dataclass(frozen=True)
class WorkflowIssue:
    severity: str
    code: str
    message: str
    entity_uid: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "entity_uid": self.entity_uid,
        }


@dataclass(frozen=True)
class PackageDocuments:
    manifest: dict
    result: dict
    assets: tuple[dict, ...]
    records: tuple[dict, ...]
    inspections: tuple[dict, ...]
    media: tuple[dict, ...]


@dataclass(frozen=True)
class PreflightResult:
    issues: tuple[WorkflowIssue, ...]
    summary: dict[str, int]
    documents: PackageDocuments | None
    task: SurveyTask | None

    @property
    def error_count(self) -> int:
        return sum(item.severity == "error" for item in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "warning" for item in self.issues)


class WorkflowStateError(ValueError):
    pass


def _issue(
    issues: list[WorkflowIssue],
    code: str,
    message: str,
    *,
    severity: str = "error",
    entity_uid: str = "",
) -> None:
    issues.append(WorkflowIssue(severity, code, message, entity_uid))


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _content_hash(value: dict, *, kind: str) -> str:
    ignored = {"created_at", "updated_at", "business_code", "code_scheme_version", "revision_no"}
    if kind == "record":
        ignored.add("source_revision_no")
    normalized = {key: item for key, item in value.items() if key not in ignored}
    return sha256(_canonical(normalized).encode("utf-8")).hexdigest()


def _load_desktop_package(path: Path, issues: list[WorkflowIssue]) -> PackageDocuments | None:
    source_text = str(DESKTOP_SRC)
    if source_text not in sys.path:
        sys.path.insert(0, source_text)
    try:
        from services.survey_result_package_reader import inspect_survey_result_package

        report = inspect_survey_result_package(path)
    except Exception as exc:
        _issue(issues, "PROTOCOL_READER_FAILED", f"桌面端协议读取器执行失败：{exc}")
        return None

    if not report.valid:
        for item in report.issues:
            _issue(
                issues,
                f"PROTOCOL_{item.code}",
                item.message,
                severity=item.severity,
                entity_uid=item.path,
            )
        return None
    if report.manifest is None or report.result is None:
        _issue(issues, "PROTOCOL_DOCUMENT_MISSING", "成果包缺少 manifest 或 result 文档。")
        return None
    return PackageDocuments(
        manifest=dict(report.manifest),
        result=dict(report.result),
        assets=tuple(dict(item) for item in report.engineering_assets),
        records=tuple(dict(item) for item in report.survey_records),
        inspections=tuple(dict(item) for item in report.inspection_results),
        media=tuple(dict(item) for item in report.survey_media),
    )


def _compare_revision(
    incoming: dict,
    existing_revision: int,
    existing_hash: str,
    *,
    kind: str,
) -> str:
    revision = max(1, int(incoming.get("revision_no") or 1))
    digest = _content_hash(incoming, kind=kind)
    if digest == existing_hash:
        return "existing"
    if revision < existing_revision:
        return "stale"
    if revision == existing_revision:
        return "conflict"
    return "update"


def evaluate_preflight(db: Session, row: ResultSubmission, path: Path) -> PreflightResult:
    issues: list[WorkflowIssue] = []
    summary = {
        "new_assets": 0,
        "existing_assets": 0,
        "updated_assets": 0,
        "stale_assets": 0,
        "conflict_assets": 0,
        "new_records": 0,
        "existing_records": 0,
        "updated_records": 0,
        "stale_records": 0,
        "conflict_records": 0,
        "new_inspections": 0,
        "existing_inspections": 0,
        "new_media": 0,
        "existing_media": 0,
    }
    if row.inspection_error_count:
        _issue(issues, "STRUCTURE_CHECK_REQUIRED", "成果包结构检查未通过，不能执行业务预检。")
        return PreflightResult(tuple(issues), summary, None, None)

    documents = _load_desktop_package(path, issues)
    if documents is None:
        return PreflightResult(tuple(issues), summary, None, None)

    submission_task_uid = str(
        documents.result.get("submission_task_uid")
        or documents.manifest.get("submission_task_uid")
        or ""
    ).strip()
    row.submission_task_uid = submission_task_uid or None
    if not submission_task_uid:
        _issue(issues, "SUBMISSION_TASK_REQUIRED", "成果包没有声明本次向中心提交所依据的任务。")
        return PreflightResult(tuple(issues), summary, documents, None)

    task = db.scalar(select(SurveyTask).where(SurveyTask.task_uid == submission_task_uid))
    if task is None:
        _issue(issues, "SUBMISSION_TASK_NOT_ISSUED", "中心没有下发过该提交任务，无法确认成果权限。", entity_uid=submission_task_uid)
        return PreflightResult(tuple(issues), summary, documents, None)
    if task.status == "cancelled":
        _issue(issues, "SUBMISSION_TASK_CANCELLED", "成果对应的调查任务已经取消。", entity_uid=submission_task_uid)

    if row.project_uid != documents.manifest.get("project_uid") or row.survey_batch_uid != documents.manifest.get("survey_batch_uid"):
        _issue(issues, "SUBMISSION_IDENTITY_CHANGED", "上传登记信息与成果包当前身份不一致。")
    project_uid = str(documents.manifest.get("project_uid") or "")
    batch_uid = str(documents.manifest.get("survey_batch_uid") or "")
    from app.models.project import Project, SurveyBatch

    project = db.get(Project, task.project_id)
    batch = db.get(SurveyBatch, task.survey_batch_id)
    if project is None or project.project_uid != project_uid:
        _issue(issues, "PROJECT_TASK_MISMATCH", "成果所属项目与中心下发任务不一致。")
    if batch is None or batch.survey_batch_uid != batch_uid:
        _issue(issues, "BATCH_TASK_MISMATCH", "成果所属调查批次与中心下发任务不一致。")

    frozen = task.frozen_snapshot_json if isinstance(task.frozen_snapshot_json, dict) else {}
    frozen_scopes = frozen.get("management_scopes") if isinstance(frozen.get("management_scopes"), list) else []
    scope_by_uid = {
        str(item.get("management_scope_uid")): item
        for item in frozen_scopes if isinstance(item, dict)
    }
    form_codes = {
        str(item.get("form_code")) for item in frozen.get("forms", [])
        if isinstance(item, dict)
    }
    asset_uids = {str(item.get("engineering_asset_uid")) for item in documents.assets}
    record_uids = {str(item.get("survey_record_uid")) for item in documents.records}
    form_code_by_asset = {
        str(item.get("engineering_asset_uid") or ""): str(
            (item.get("form") if isinstance(item.get("form"), dict) else {}).get("form_code") or ""
        )
        for item in documents.records
    }

    for record in documents.records:
        uid = str(record.get("survey_record_uid") or "")
        scope_uid = str(record.get("source_management_scope_uid") or "")
        source_task_uid = str(record.get("source_task_uid") or "")
        scope = scope_by_uid.get(scope_uid)
        if scope is None:
            _issue(issues, "RECORD_SCOPE_NOT_AUTHORIZED", "调查记录不在任务冻结的授权范围内。", entity_uid=uid)
            continue
        if record.get("organization_unit_uid") != scope.get("organization_unit_uid"):
            _issue(issues, "RECORD_SCOPE_OWNER_MISMATCH", "调查记录管理单位与冻结分管范围不一致。", entity_uid=uid)
        if record.get("canal_unit_uid") != scope.get("canal_uid"):
            _issue(issues, "RECORD_SCOPE_CANAL_MISMATCH", "调查记录渠道与冻结分管范围不一致。", entity_uid=uid)
        if not source_task_uid:
            _issue(issues, "RECORD_SOURCE_TASK_REQUIRED", "调查记录缺少真实来源任务。", entity_uid=uid)
        elif task.target_unit_type == "water_office" and source_task_uid != task.task_uid:
            _issue(issues, "RECORD_SOURCE_TASK_MISMATCH", "水管所直达任务成果的来源任务不一致。", entity_uid=uid)
        if record.get("project_uid") != project_uid or record.get("survey_batch_uid") != batch_uid:
            _issue(issues, "RECORD_BATCH_MISMATCH", "调查记录所属项目或批次与成果包不一致。", entity_uid=uid)
        form = record.get("form") if isinstance(record.get("form"), dict) else {}
        if form.get("form_code") not in form_codes:
            _issue(issues, "RECORD_FORM_NOT_AUTHORIZED", "调查记录使用了任务未冻结的表单。", entity_uid=uid)
        if record.get("engineering_asset_uid") not in asset_uids:
            _issue(issues, "RECORD_ASSET_MISSING", "调查记录引用的工程对象不在成果包内。", entity_uid=uid)
        if record.get("record_status") != "completed":
            _issue(issues, "RECORD_NOT_COMPLETED", "成果包只能提交已完成调查记录。", entity_uid=uid)

    for item in documents.inspections:
        if str(item.get("survey_record_uid") or "") not in record_uids:
            _issue(issues, "INSPECTION_RECORD_MISSING", "分项评价引用的调查记录不在成果包内。")
    for item in documents.media:
        if str(item.get("survey_record_uid") or "") not in record_uids:
            _issue(issues, "MEDIA_RECORD_MISSING", "影像引用的调查记录不在成果包内。")

    incoming_asset_uids = [str(item.get("engineering_asset_uid") or "") for item in documents.assets]
    existing_assets = {
        item.engineering_asset_uid: item
        for item in db.scalars(
            select(CentralEngineeringAsset).where(CentralEngineeringAsset.engineering_asset_uid.in_(incoming_asset_uids))
        )
    } if incoming_asset_uids else {}
    for item in documents.assets:
        uid = str(item.get("engineering_asset_uid") or "")
        existing = existing_assets.get(uid)
        if existing is None:
            name = str(item.get("asset_name") or "").strip()
            duplicate = None
            if name:
                duplicate = db.scalar(
                    select(CentralEngineeringAsset).where(
                        CentralEngineeringAsset.engineering_asset_uid != uid,
                        CentralEngineeringAsset.project_uid == str(item.get("project_uid") or ""),
                        CentralEngineeringAsset.asset_type == item.get("asset_type"),
                        CentralEngineeringAsset.organization_unit_uid == item.get("organization_unit_uid"),
                        CentralEngineeringAsset.canal_unit_uid == item.get("canal_unit_uid"),
                        func.lower(CentralEngineeringAsset.asset_name) == name.lower(),
                    )
                )
                pending_web = db.scalar(
                    select(OnlineSurveyEntry).where(
                        OnlineSurveyEntry.project_uid == str(item.get("project_uid") or ""),
                        OnlineSurveyEntry.organization_unit_uid == item.get("organization_unit_uid"),
                        OnlineSurveyEntry.canal_unit_uid == item.get("canal_unit_uid"),
                        OnlineSurveyEntry.form_code == form_code_by_asset.get(uid, ""),
                        func.lower(OnlineSurveyEntry.asset_name) == name.lower(),
                        OnlineSurveyEntry.status.in_(("submitted", "accepted")),
                    )
                )
                if duplicate is not None or pending_web is not None:
                    _issue(issues, "ASSET_POSSIBLE_DUPLICATE", "中心已有相同项目、渠道、单位和名称的调查对象，请核对后再入库，避免 Web 与桌面端重复建档。", entity_uid=uid)
            summary["new_assets"] += 1
            continue
        state = _compare_revision(item, existing.revision_no, existing.content_sha256, kind="asset")
        summary[f"{state}_assets"] += 1
        if state == "stale":
            _issue(issues, "ASSET_STALE", "工程对象版本早于中心现有版本。", entity_uid=uid)
        elif state == "conflict":
            _issue(issues, "ASSET_REVISION_CONFLICT", "工程对象同一版本包含不同内容。", entity_uid=uid)

    incoming_record_uids = [str(item.get("survey_record_uid") or "") for item in documents.records]
    existing_records = {
        item.survey_record_uid: item
        for item in db.scalars(
            select(CentralSurveyRecord).where(CentralSurveyRecord.survey_record_uid.in_(incoming_record_uids))
        )
    } if incoming_record_uids else {}
    for item in documents.records:
        uid = str(item.get("survey_record_uid") or "")
        existing = existing_records.get(uid)
        if existing is None:
            summary["new_records"] += 1
            continue
        state = _compare_revision(item, existing.revision_no, existing.content_sha256, kind="record")
        summary[f"{state}_records"] += 1
        if state == "stale":
            _issue(issues, "RECORD_STALE", "调查记录版本早于中心现有版本。", entity_uid=uid)
        elif state == "conflict":
            _issue(issues, "RECORD_REVISION_CONFLICT", "调查记录同一版本包含不同内容。", entity_uid=uid)

    inspection_keys = [(str(item.get("survey_record_uid") or ""), str(item.get("item_code") or "")) for item in documents.inspections]
    for record_uid, item_code in inspection_keys:
        existing = db.scalar(
            select(CentralInspectionResult).where(
                CentralInspectionResult.survey_record_uid == record_uid,
                CentralInspectionResult.item_code == item_code,
            )
        )
        summary["existing_inspections" if existing else "new_inspections"] += 1

    media_uids = [str(item.get("media_uid") or "") for item in documents.media]
    existing_media = set(
        db.scalars(select(CentralSurveyMedia.media_uid).where(CentralSurveyMedia.media_uid.in_(media_uids)))
    ) if media_uids else set()
    for uid in media_uids:
        summary["existing_media" if uid in existing_media else "new_media"] += 1

    return PreflightResult(tuple(issues), summary, documents, task)


def run_preflight(db: Session, row: ResultSubmission, path: Path) -> PreflightResult:
    if row.status == "imported":
        raise WorkflowStateError("已经正式入库的成果不能重新预检。")
    result = evaluate_preflight(db, row, path)
    row.preflight_error_count = result.error_count
    row.preflight_warning_count = result.warning_count
    row.preflight_issues_json = [item.as_dict() for item in result.issues]
    row.preflight_summary_json = result.summary
    row.preflight_checked_at = datetime.now().astimezone()
    row.status = "preflight_passed" if result.error_count == 0 else "conflict"
    if result.error_count == 0 and result.task is not None and result.task.status not in {"cancelled", "closed"}:
        result.task.status = "result_received"
    db.commit()
    db.refresh(row)
    return result


def review_submission(
    db: Session,
    row: ResultSubmission,
    *,
    decision: str,
    notes: str | None,
    reviewer: User,
) -> ResultSubmission:
    if decision not in {"accepted", "rejected"}:
        raise ValueError("审核结论无效。")
    if decision == "accepted" and row.status not in {"preflight_passed", "reviewing", "accepted"}:
        raise WorkflowStateError("只有业务预检通过的成果才能审核接收。")
    if decision == "rejected" and row.status == "imported":
        raise WorkflowStateError("已经正式入库的成果不能退回。")
    row.status = decision
    row.review_notes = notes.strip() if notes else None
    row.reviewed_by_user_uid = reviewer.user_uid
    row.reviewed_by_username = reviewer.username
    row.reviewed_at = datetime.now().astimezone()
    db.commit()
    db.refresh(row)
    return row


def import_submission(db: Session, row: ResultSubmission, path: Path) -> dict[str, int]:
    if row.status != "accepted":
        raise WorkflowStateError("只有审核接收的成果才能正式入库。")
    preflight = evaluate_preflight(db, row, path)
    if preflight.error_count or preflight.documents is None:
        raise WorkflowStateError("成果在入库前复检发现问题，请重新执行业务预检。")
    documents = preflight.documents
    changed_records: set[str] = set()
    incoming_record_uids: set[str] = {
        str(item["survey_record_uid"])
        for item in documents.records
    }

    for item in documents.assets:
        uid = str(item["engineering_asset_uid"])
        existing = db.scalar(select(CentralEngineeringAsset).where(CentralEngineeringAsset.engineering_asset_uid == uid))
        digest = _content_hash(item, kind="asset")
        if existing is None:
            existing = CentralEngineeringAsset(engineering_asset_uid=uid)
            db.add(existing)
        elif digest == existing.content_sha256:
            continue
        existing.project_uid = str(item["project_uid"])
        existing.asset_name = item.get("asset_name")
        existing.asset_type = item.get("asset_type")
        existing.organization_unit_uid = item.get("organization_unit_uid")
        existing.canal_unit_uid = item.get("canal_unit_uid")
        existing.business_code = item.get("business_code")
        existing.revision_no = max(1, int(item.get("revision_no") or 1))
        existing.content_sha256 = digest
        existing.payload_json = item
        existing.current_submission_uid = row.submission_uid

    for item in documents.records:
        uid = str(item["survey_record_uid"])
        existing = db.scalar(select(CentralSurveyRecord).where(CentralSurveyRecord.survey_record_uid == uid))
        digest = _content_hash(item, kind="record")
        if existing is not None and digest == existing.content_sha256:
            continue
        if existing is None:
            existing = CentralSurveyRecord(survey_record_uid=uid, imported_at=datetime.now().astimezone())
            db.add(existing)
        form = item.get("form") if isinstance(item.get("form"), dict) else {}
        existing.engineering_asset_uid = str(item["engineering_asset_uid"])
        existing.project_uid = str(item["project_uid"])
        existing.survey_batch_uid = str(item["survey_batch_uid"])
        existing.form_code = str(form.get("form_code") or "")
        existing.organization_unit_uid = str(item["organization_unit_uid"])
        existing.canal_unit_uid = str(item["canal_unit_uid"])
        existing.source_task_uid = item.get("source_task_uid")
        existing.source_management_scope_uid = item.get("source_management_scope_uid")
        existing.record_status = item.get("record_status")
        existing.revision_no = max(1, int(item.get("revision_no") or 1))
        existing.content_sha256 = digest
        existing.payload_json = item
        existing.current_submission_uid = row.submission_uid
        changed_records.add(uid)

    # 分项评价和影像没有独立版本号。每次正式导入都以成果包中的
    # 完整子集合替换中心现有值，避免主记录未变时遗漏子项更新。
    if incoming_record_uids:
        db.execute(
            delete(CentralInspectionResult).where(
                CentralInspectionResult.survey_record_uid.in_(incoming_record_uids)
            )
        )
        db.execute(
            delete(CentralSurveyMedia).where(
                CentralSurveyMedia.survey_record_uid.in_(incoming_record_uids)
            )
        )
        db.flush()
    for item in documents.inspections:
        if str(item.get("survey_record_uid")) in incoming_record_uids:
            db.add(CentralInspectionResult(
                survey_record_uid=str(item["survey_record_uid"]),
                item_code=str(item["item_code"]),
                payload_json=item,
                current_submission_uid=row.submission_uid,
            ))
    for item in documents.media:
        if str(item.get("survey_record_uid")) in incoming_record_uids:
            db.add(CentralSurveyMedia(
                media_uid=str(item["media_uid"]),
                survey_record_uid=str(item["survey_record_uid"]),
                package_path=str(item["package_path"]),
                file_sha256=str(item["file_sha256"]),
                file_size=int(item["file_size"]),
                payload_json=item,
                current_submission_uid=row.submission_uid,
            ))

    row.status = "imported"
    row.imported_at = datetime.now().astimezone()
    if preflight.task is not None:
        preflight.task.status = "closed"
    db.commit()
    return {
        "assets": len(documents.assets),
        "records": len(documents.records),
        "inspections": len(documents.inspections),
        "media": len(documents.media),
        "changed_records": len(changed_records),
    }
