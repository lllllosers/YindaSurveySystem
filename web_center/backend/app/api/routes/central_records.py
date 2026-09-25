from __future__ import annotations

import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_permission
from app.db.session import get_db
from app.models.auth import User
from app.models.central_record import CentralEngineeringAsset, CentralSurveyRecord
from app.schemas.central_record import (
    CentralRecordDetail,
    CentralRecordPage,
    CentralRecordRead,
    CentralRecordSummary,
)
from app.services import central_record_service
from app.services.master_data_service import get_snapshot


router = APIRouter(prefix="/central-records", tags=["Central Records"])
DbSession = Annotated[Session, Depends(get_db)]
RecordReader = Annotated[User, Depends(require_permission("central_records.read"))]


def _csv_cell(value: object) -> object:
    """Prevent spreadsheet software from evaluating user-controlled formulas."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _name_maps() -> tuple[dict[str, str], dict[str, str]]:
    snapshot = get_snapshot()
    organizations = {
        item.stable_uid: item.name
        for item in [*snapshot.departments, *snapshot.offices]
    }
    canals = {item.stable_uid: item.name for item in snapshot.canals}
    return organizations, canals


def to_read(
    record: CentralSurveyRecord,
    asset: CentralEngineeringAsset,
) -> CentralRecordRead:
    organizations, canals = _name_maps()
    return CentralRecordRead(
        survey_record_uid=record.survey_record_uid,
        engineering_asset_uid=record.engineering_asset_uid,
        asset_name=asset.asset_name,
        asset_type=asset.asset_type,
        business_code=asset.business_code,
        project_uid=record.project_uid,
        survey_batch_uid=record.survey_batch_uid,
        form_code=record.form_code,
        organization_unit_uid=record.organization_unit_uid,
        organization_name=organizations.get(record.organization_unit_uid, record.organization_unit_uid),
        canal_unit_uid=record.canal_unit_uid,
        canal_name=canals.get(record.canal_unit_uid, record.canal_unit_uid),
        source_task_uid=record.source_task_uid,
        source_management_scope_uid=record.source_management_scope_uid,
        record_status=record.record_status,
        revision_no=record.revision_no,
        current_submission_uid=record.current_submission_uid,
        imported_at=record.imported_at,
        updated_at=record.updated_at,
    )


def _query(
    db: Session,
    *,
    project_uid: str | None,
    survey_batch_uid: str | None,
    form_code: str | None,
    organization_unit_uid: str | None,
    canal_unit_uid: str | None,
    search: str | None,
    limit: int,
    offset: int,
):
    return central_record_service.list_records(
        db,
        project_uid=project_uid,
        survey_batch_uid=survey_batch_uid,
        form_code=form_code,
        organization_unit_uid=organization_unit_uid,
        canal_unit_uid=canal_unit_uid,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/summary", response_model=CentralRecordSummary)
def get_summary(_: RecordReader, db: DbSession):
    return central_record_service.summary(db)


@router.get("/export.csv")
def export_records(
    _: RecordReader,
    db: DbSession,
    project_uid: str | None = None,
    survey_batch_uid: str | None = None,
    form_code: str | None = None,
    organization_unit_uid: str | None = None,
    canal_unit_uid: str | None = None,
    search: str | None = None,
):
    rows, _ = _query(
        db,
        project_uid=project_uid,
        survey_batch_uid=survey_batch_uid,
        form_code=form_code,
        organization_unit_uid=organization_unit_uid,
        canal_unit_uid=canal_unit_uid,
        search=search,
        limit=100000,
        offset=0,
    )
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "调查记录UID", "工程名称", "工程类型", "业务编号", "表单代码",
        "管理单位", "渠道", "记录状态", "版本", "来源任务UID", "成果提交UID",
    ])
    for record, asset in rows:
        item = to_read(record, asset)
        writer.writerow([_csv_cell(value) for value in [
            item.survey_record_uid, item.asset_name, item.asset_type, item.business_code,
            item.form_code, item.organization_name, item.canal_name, item.record_status,
            item.revision_no, item.source_task_uid, item.current_submission_uid,
        ]])
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="central-records.csv"'},
    )


@router.get("", response_model=CentralRecordPage)
def get_records(
    _: RecordReader,
    db: DbSession,
    project_uid: str | None = None,
    survey_batch_uid: str | None = None,
    form_code: str | None = None,
    organization_unit_uid: str | None = None,
    canal_unit_uid: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    rows, total = _query(
        db,
        project_uid=project_uid,
        survey_batch_uid=survey_batch_uid,
        form_code=form_code,
        organization_unit_uid=organization_unit_uid,
        canal_unit_uid=canal_unit_uid,
        search=search,
        limit=limit,
        offset=offset,
    )
    return CentralRecordPage(
        items=[to_read(record, asset) for record, asset in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{survey_record_uid}", response_model=CentralRecordDetail)
def get_record(survey_record_uid: str, _: RecordReader, db: DbSession):
    result = central_record_service.get_record(db, survey_record_uid)
    if result is None:
        raise HTTPException(status_code=404, detail="Central record not found.")
    record, asset, inspections, media = result
    return CentralRecordDetail(
        **to_read(record, asset).model_dump(),
        record_payload=record.payload_json,
        asset_payload=asset.payload_json,
        inspections=[item.payload_json for item in inspections],
        media=[item.payload_json for item in media],
    )
