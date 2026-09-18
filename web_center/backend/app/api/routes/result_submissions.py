from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_permission
from app.db.session import get_db
from app.models.auth import User
from app.models.result_submission import ResultSubmission
from app.schemas.result_submission import PackageIssueRead, ResultSubmissionPage, ResultSubmissionRead
from app.services import result_submission_service


router = APIRouter(prefix="/result-submissions", tags=["Result Submissions"])
DbSession = Annotated[Session, Depends(get_db)]
ResultReader = Annotated[User, Depends(require_permission("results.read"))]
ResultUploader = Annotated[User, Depends(require_permission("results.upload"))]


def to_read(row: ResultSubmission) -> ResultSubmissionRead:
    issues = row.inspection_issues_json if isinstance(row.inspection_issues_json, list) else []
    counts = row.counts_json if isinstance(row.counts_json, dict) else {}
    source_task_uids = row.source_task_uids if isinstance(row.source_task_uids, list) else []

    return ResultSubmissionRead(
        submission_uid=row.submission_uid,
        package_uid=row.package_uid,
        result_uid=row.result_uid,
        project_uid=row.project_uid,
        survey_batch_uid=row.survey_batch_uid,
        original_filename=row.original_filename,
        file_sha256=row.file_sha256,
        file_size=row.file_size,
        package_format_version=row.package_format_version,
        desktop_app_version=row.desktop_app_version,
        desktop_app_version_label=row.desktop_app_version_label,
        result_name=row.result_name,
        source_task_uids=[str(v) for v in source_task_uids],
        counts=counts,
        status=row.status,
        inspection_error_count=row.inspection_error_count,
        inspection_issues=[
            PackageIssueRead(
                code=str(item.get("code", "")),
                message=str(item.get("message", "")),
                path=str(item["path"]) if item.get("path") is not None else None,
            )
            for item in issues
            if isinstance(item, dict)
        ],
        uploader_user_uid=row.uploader_user_uid,
        uploader_username=row.uploader_username,
        uploaded_at=row.uploaded_at,
    )


@router.get("", response_model=ResultSubmissionPage)
def get_submissions(
    _: ResultReader,
    db: DbSession,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    rows, total = result_submission_service.list_submissions(
        db,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return ResultSubmissionPage(
        items=[to_read(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/upload",
    response_model=ResultSubmissionRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_result(
    request: Request,
    uploader: ResultUploader,
    db: DbSession,
    file: UploadFile = File(...),
):
    try:
        row, reused = await result_submission_service.receive_submission(
            db,
            upload=file,
            uploader=uploader,
        )
    except result_submission_service.UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except (
        result_submission_service.DuplicatePackageConflictError,
        result_submission_service.DuplicateResultError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    request.state.audit_summary = (
        "重复成果包，返回既有提交"
        if reused
        else (
            "成果包上传并完成结构检查"
            if row.status == "inspected"
            else "成果包上传完成，但结构检查未通过"
        )
    )
    request.state.audit_details = {
        "submission_uid": row.submission_uid,
        "package_uid": row.package_uid,
        "result_uid": row.result_uid,
        "status": row.status,
        "file_sha256": row.file_sha256,
        "file_size": row.file_size,
        "reused": reused,
    }

    return to_read(row)


@router.get("/{submission_uid}", response_model=ResultSubmissionRead)
def get_submission(
    submission_uid: str,
    _: ResultReader,
    db: DbSession,
):
    row = result_submission_service.get_submission(db, submission_uid)
    if row is None:
        raise HTTPException(status_code=404, detail="Submission not found.")
    return to_read(row)


@router.get("/{submission_uid}/download")
def download_submission(
    submission_uid: str,
    _: ResultReader,
    db: DbSession,
):
    row = result_submission_service.get_submission(db, submission_uid)
    if row is None:
        raise HTTPException(status_code=404, detail="Submission not found.")

    try:
        path = result_submission_service.submission_file_path(row)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc

    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=row.original_filename,
    )
