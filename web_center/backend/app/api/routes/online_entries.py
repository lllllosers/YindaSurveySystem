import mimetypes
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_permission
from app.db.session import get_db
from app.models.auth import User
from app.models.online_entry import OnlineSurveyEntry
from app.models.project import Project, SurveyBatch
from app.models.survey_task import SurveyTask
from app.schemas.online_entry import (
    OnlineEntryPage,
    OnlineEntryPayload,
    OnlineEntryRead,
    OnlineEntryReview,
    OnlineEntryUpdate,
    OnlineFormDefinitionRead,
    OnlineMediaRead,
)
from app.services import online_entry_service


router = APIRouter(prefix="/online-entries", tags=["Online Survey Entries"])
DbSession = Annotated[Session, Depends(get_db)]
EntryReader = Annotated[User, Depends(require_permission("online_entries.read"))]
EntryWriter = Annotated[User, Depends(require_permission("online_entries.write"))]
EntryReviewer = Annotated[User, Depends(require_permission("online_entries.review"))]


def _context(db: Session, row: OnlineSurveyEntry) -> tuple[SurveyTask, Project, SurveyBatch]:
    result = db.execute(
        select(SurveyTask, Project, SurveyBatch)
        .select_from(SurveyTask)
        .join(Project, Project.project_uid == row.project_uid)
        .join(SurveyBatch, SurveyBatch.survey_batch_uid == row.survey_batch_uid)
        .where(SurveyTask.task_uid == row.task_uid)
    ).one()
    return result


def to_read(row: OnlineSurveyEntry, task: SurveyTask, project: Project, batch: SurveyBatch) -> OnlineEntryRead:
    return OnlineEntryRead(
        entry_uid=row.entry_uid,
        task_uid=row.task_uid,
        task_name=task.task_name,
        project_uid=row.project_uid,
        project_name=project.name,
        survey_batch_uid=row.survey_batch_uid,
        batch_name=batch.batch_name,
        management_scope_uid=row.management_scope_uid,
        organization_unit_uid=row.organization_unit_uid,
        organization_name=row.organization_name,
        canal_unit_uid=row.canal_unit_uid,
        canal_name=row.canal_name,
        form_code=row.form_code,
        form_name=row.form_name,
        asset_name=row.asset_name,
        form_data=row.form_data_json,
        evaluations=row.evaluations_json,
        conclusion=row.conclusion_json,
        media=[OnlineMediaRead.model_validate(item) for item in (row.media_json or [])],
        status=row.status,
        revision_no=row.revision_no,
        review_notes=row.review_notes,
        created_by_username=row.created_by_username,
        submitted_at=row.submitted_at,
        reviewed_by_username=row.reviewed_by_username,
        reviewed_at=row.reviewed_at,
        imported_at=row.imported_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def require_entry(db: Session, entry_uid: str) -> OnlineSurveyEntry:
    row = online_entry_service.get_entry(db, entry_uid)
    if row is None:
        raise HTTPException(status_code=404, detail="调查记录不存在。")
    return row


def require_owner(row: OnlineSurveyEntry, user: User) -> None:
    if user.role != "admin" and row.created_by_user_uid != user.user_uid:
        raise HTTPException(status_code=403, detail="只能修改本人创建的调查记录。")


@router.get("/form-definitions", response_model=list[OnlineFormDefinitionRead])
def get_form_definitions(_: EntryReader):
    return online_entry_service.form_definitions()


@router.get("", response_model=OnlineEntryPage)
def get_entries(
    current_user: EntryReader,
    db: DbSession,
    status_filter: str | None = Query(default=None, alias="status"),
    task_uid: str | None = None,
    mine: bool = False,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    rows, total = online_entry_service.list_entries(
        db,
        status=status_filter,
        task_uid=task_uid,
        creator_uid=current_user.user_uid if mine else None,
        limit=limit,
        offset=offset,
    )
    return OnlineEntryPage(
        items=[to_read(row, task, project, batch) for row, task, project, batch in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=OnlineEntryRead, status_code=status.HTTP_201_CREATED)
def post_entry(payload: OnlineEntryPayload, request: Request, creator: EntryWriter, db: DbSession):
    try:
        row = online_entry_service.create_entry(db, payload, creator)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    request.state.audit_summary = "新建在线调查记录草稿"
    request.state.audit_details = {"entry_uid": row.entry_uid, "form_code": row.form_code}
    return to_read(row, *_context(db, row))


@router.get("/{entry_uid}", response_model=OnlineEntryRead)
def get_entry(entry_uid: str, _: EntryReader, db: DbSession):
    row = require_entry(db, entry_uid)
    return to_read(row, *_context(db, row))


@router.post("/{entry_uid}/media", response_model=OnlineMediaRead, status_code=status.HTTP_201_CREATED)
async def upload_entry_media(
    entry_uid: str,
    request: Request,
    user: EntryWriter,
    db: DbSession,
    file: UploadFile = File(...),
    media_role: str = Form(default="现场记录"),
    part_name: str | None = Form(default=None),
    notes: str | None = Form(default=None),
):
    row = require_entry(db, entry_uid)
    require_owner(row, user)
    try:
        item = await online_entry_service.add_media(
            db,
            row,
            upload=file,
            media_role=media_role,
            part_name=part_name,
            notes=notes,
        )
    except online_entry_service.MediaUploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except online_entry_service.OnlineEntryStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    request.state.audit_summary = "上传在线调查影像"
    request.state.audit_details = {
        "entry_uid": entry_uid,
        "media_uid": item["media_uid"],
        "media_kind": item["media_kind"],
        "file_size": item["file_size"],
    }
    return OnlineMediaRead.model_validate(item)


@router.get("/{entry_uid}/media/{media_uid}")
def download_entry_media(entry_uid: str, media_uid: str, _: EntryReader, db: DbSession):
    row = require_entry(db, entry_uid)
    item = next(
        (value for value in (row.media_json or []) if value.get("media_uid") == media_uid),
        None,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="没有找到该调查影像。")
    try:
        path = online_entry_service.online_media_path(item)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    media_type = mimetypes.guess_type(str(item.get("original_filename") or path.name))[0]
    return FileResponse(
        path,
        media_type=media_type or "application/octet-stream",
        filename=str(item.get("original_filename") or path.name),
        content_disposition_type="inline",
    )


@router.delete("/{entry_uid}/media/{media_uid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry_media(
    entry_uid: str,
    media_uid: str,
    request: Request,
    user: EntryWriter,
    db: DbSession,
):
    row = require_entry(db, entry_uid)
    require_owner(row, user)
    try:
        online_entry_service.remove_media(db, row, media_uid)
    except online_entry_service.OnlineEntryStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    request.state.audit_summary = "删除在线调查影像"
    request.state.audit_details = {"entry_uid": entry_uid, "media_uid": media_uid}


@router.put("/{entry_uid}", response_model=OnlineEntryRead)
def put_entry(
    entry_uid: str, payload: OnlineEntryUpdate, request: Request, user: EntryWriter, db: DbSession
):
    row = require_entry(db, entry_uid)
    require_owner(row, user)
    try:
        online_entry_service.update_entry(db, row, payload)
    except online_entry_service.OnlineEntryStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    request.state.audit_summary = "保存在线调查记录草稿"
    request.state.audit_details = {"entry_uid": row.entry_uid, "revision_no": row.revision_no}
    return to_read(row, *_context(db, row))


@router.post("/{entry_uid}/submit", response_model=OnlineEntryRead)
def submit_entry(entry_uid: str, request: Request, user: EntryWriter, db: DbSession):
    row = require_entry(db, entry_uid)
    require_owner(row, user)
    try:
        online_entry_service.submit_entry(db, row)
    except online_entry_service.OnlineEntryStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    request.state.audit_summary = "提交在线调查记录审核"
    request.state.audit_details = {"entry_uid": row.entry_uid, "form_code": row.form_code}
    return to_read(row, *_context(db, row))


@router.post("/{entry_uid}/review", response_model=OnlineEntryRead)
def review_entry(
    entry_uid: str, payload: OnlineEntryReview, request: Request, reviewer: EntryReviewer, db: DbSession
):
    row = require_entry(db, entry_uid)
    try:
        if payload.decision == "accept":
            online_entry_service.accept_and_import(db, row, reviewer, payload.notes)
            summary = "审核通过在线调查记录并入库"
        else:
            online_entry_service.reject_entry(db, row, reviewer, payload.notes or "")
            summary = "退回在线调查记录"
    except online_entry_service.OnlineEntryStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    request.state.audit_summary = summary
    request.state.audit_details = {"entry_uid": row.entry_uid, "decision": payload.decision}
    db.refresh(row)
    return to_read(row, *_context(db, row))
