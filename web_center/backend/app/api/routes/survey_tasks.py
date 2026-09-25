from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_permission
from app.db.session import get_db
from app.models.auth import User
from app.models.project import Project, SurveyBatch
from app.models.survey_task import SurveyTask
from app.schemas.survey_task import (
    FrozenScopeRead,
    SurveyTaskCreate,
    SurveyTaskDetail,
    SurveyTaskPage,
    SurveyTaskRead,
)
from app.services import survey_task_service


router = APIRouter(prefix="/survey-tasks", tags=["Survey Tasks"])
DbSession = Annotated[Session, Depends(get_db)]
TaskReader = Annotated[User, Depends(require_permission("tasks.read"))]
TaskWriter = Annotated[User, Depends(require_permission("tasks.write"))]
TaskDownloader = Annotated[User, Depends(require_permission("tasks.download"))]


def to_read(row: SurveyTask, project: Project, batch: SurveyBatch) -> SurveyTaskRead:
    return SurveyTaskRead(
        task_uid=row.task_uid,
        package_uid=row.package_uid,
        project_uid=project.project_uid,
        project_name=project.name,
        survey_batch_uid=batch.survey_batch_uid,
        batch_name=batch.batch_name,
        batch_code=batch.batch_code,
        task_name=row.task_name,
        notes=row.notes,
        target_unit_type=row.target_unit_type,
        department_uid=row.department_uid,
        department_name=row.department_name,
        organization_unit_uid=row.organization_unit_uid,
        organization_name=row.organization_name,
        parent_task_uid=row.parent_task_uid,
        root_task_uid=row.root_task_uid,
        task_depth=row.task_depth,
        selected_scope_count=row.selected_scope_count,
        reference_canal_count=row.reference_canal_count,
        reference_organization_count=row.reference_organization_count,
        form_count=row.form_count,
        file_sha256=row.file_sha256,
        file_size=row.file_size,
        status=row.status,
        download_count=row.download_count,
        first_downloaded_at=row.first_downloaded_at,
        last_downloaded_at=row.last_downloaded_at,
        created_by_username=row.created_by_username,
        created_at=row.created_at,
    )


def require_task(db: Session, task_uid: str) -> tuple[SurveyTask, Project, SurveyBatch]:
    result = survey_task_service.get_task(db, task_uid)
    if result is None:
        raise HTTPException(status_code=404, detail="Survey task not found.")
    return result


@router.get("", response_model=SurveyTaskPage)
def get_tasks(
    _: TaskReader,
    db: DbSession,
    project_uid: str | None = None,
    survey_batch_uid: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    rows, total = survey_task_service.list_tasks(
        db,
        project_uid=project_uid,
        survey_batch_uid=survey_batch_uid,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return SurveyTaskPage(
        items=[to_read(row, project, batch) for row, project, batch in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=SurveyTaskDetail, status_code=status.HTTP_201_CREATED)
def post_task(payload: SurveyTaskCreate, request: Request, creator: TaskWriter, db: DbSession):
    try:
        row = survey_task_service.create_task(db, payload, creator)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    project = db.get(Project, row.project_id)
    batch = db.get(SurveyBatch, row.survey_batch_id)
    assert project is not None and batch is not None
    request.state.audit_summary = "生成并登记调查任务包"
    request.state.audit_details = {
        "task_uid": row.task_uid,
        "package_uid": row.package_uid,
        "target_unit_type": row.target_unit_type,
        "organization_name": row.organization_name,
        "selected_scope_count": row.selected_scope_count,
    }
    return to_detail(row, project, batch)


def to_detail(row: SurveyTask, project: Project, batch: SurveyBatch) -> SurveyTaskDetail:
    base = to_read(row, project, batch).model_dump()
    frozen = row.frozen_snapshot_json if isinstance(row.frozen_snapshot_json, dict) else {}
    scopes = frozen.get("management_scopes")
    if not isinstance(scopes, list):
        scopes = []
    return SurveyTaskDetail(
        **base,
        selected_management_scope_uids=[str(v) for v in row.selected_scope_uids],
        frozen_scopes=[FrozenScopeRead.model_validate(item) for item in scopes],
        master_data_version=str(frozen.get("master_data_version", "")),
        master_contract_sha256=str(frozen.get("master_contract_sha256", "")),
        form_contract_version=str(frozen.get("form_contract_version", "")),
    )


@router.get("/{task_uid}", response_model=SurveyTaskDetail)
def get_task(task_uid: str, _: TaskReader, db: DbSession):
    row, project, batch = require_task(db, task_uid)
    return to_detail(row, project, batch)


@router.get("/{task_uid}/download")
def download_task(task_uid: str, request: Request, _: TaskDownloader, db: DbSession):
    row, _project, batch = require_task(db, task_uid)
    if row.status == "cancelled":
        raise HTTPException(status_code=409, detail="Cancelled task cannot be downloaded.")
    try:
        path = survey_task_service.task_file_path(row)
    except survey_task_service.TaskFileMissingError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    survey_task_service.register_download(db, row)
    request.state.audit_summary = "下载调查任务包"
    request.state.audit_details = {"task_uid": task_uid, "download_count": row.download_count}
    return FileResponse(
        path,
        media_type="application/zip",
        filename=survey_task_service.safe_download_name(row, batch),
    )


@router.post("/{task_uid}/cancel", response_model=SurveyTaskRead)
def cancel_task(task_uid: str, request: Request, _: TaskWriter, db: DbSession):
    row, project, batch = require_task(db, task_uid)
    try:
        survey_task_service.cancel_task(db, row)
    except survey_task_service.TaskStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    request.state.audit_summary = "取消调查任务"
    request.state.audit_details = {"task_uid": task_uid}
    return to_read(row, project, batch)
