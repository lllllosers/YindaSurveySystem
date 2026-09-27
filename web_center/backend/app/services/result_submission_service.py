from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
import shutil
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.core.config import settings
from app.services.disk_space import require_free_space
from app.models.central_record import CentralEngineeringAsset, CentralSurveyRecord
from app.models.result_submission import ResultSubmission
from app.models.survey_task import SurveyTask
from app.services.result_package_inspection import inspect_result_package


BACKEND_ROOT = Path(__file__).resolve().parents[2]
STORAGE_ROOT = BACKEND_ROOT / "storage"
INCOMING_DIR = STORAGE_ROOT / "incoming"
SUBMISSIONS_DIR = STORAGE_ROOT / "result_submissions"

CHUNK_SIZE = 1024 * 1024


class UploadTooLargeError(ValueError):
    pass


class DuplicatePackageConflictError(ValueError):
    pass


class DuplicateResultError(ValueError):
    pass


class SubmissionDeleteError(ValueError):
    pass


def ensure_storage() -> None:
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)


async def save_upload(upload: UploadFile, target: Path) -> tuple[str, int]:
    digest = sha256()
    size = 0
    require_free_space(target.parent, upload.size or 0)
    with target.open("wb") as output:
        while True:
            chunk = await upload.read(CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            if size > settings.max_result_upload_bytes:
                raise UploadTooLargeError("上传文件超过当前安全上限。")
            if upload.size is None:
                require_free_space(target.parent, len(chunk))
            digest.update(chunk)
            output.write(chunk)
    return digest.hexdigest(), size


def get_submission(db: Session, submission_uid: str) -> ResultSubmission | None:
    return db.scalar(
        select(ResultSubmission).where(
            ResultSubmission.submission_uid == submission_uid
        )
    )


def delete_unprocessed_submission(db: Session, row: ResultSubmission) -> None:
    if row.status not in {"uploaded", "inspected", "invalid", "conflict"}:
        raise SubmissionDeleteError("已进入审核或正式入库流程的成果包不能删除，请保留历史记录。")
    if any(db.scalar(select(model.id).where(model.current_submission_uid == row.submission_uid).limit(1)) is not None
           for model in (CentralEngineeringAsset, CentralSurveyRecord)):
        raise SubmissionDeleteError("成果包已被正式成果引用，不能删除。")
    path = (BACKEND_ROOT / row.stored_relative_path).resolve()
    root = SUBMISSIONS_DIR.resolve()
    if root not in path.parents or path.name != "package.ydresult":
        raise SubmissionDeleteError("成果包存储路径异常，拒绝删除。")
    db.delete(row)
    db.commit()
    path.unlink(missing_ok=True)
    try:
        path.parent.rmdir()
    except OSError:
        pass


def list_submissions(
    db: Session,
    *,
    status: str | None,
    queue: str | None = None,
    project_uid: str | None,
    survey_batch_uid: str | None,
    keyword: str | None,
    office_scope_uid: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ResultSubmission], int, dict[str, int]]:
    context_filters = []
    if office_scope_uid:
        scoped_task = select(SurveyTask.id).where(
            SurveyTask.task_uid == ResultSubmission.submission_task_uid,
            SurveyTask.target_unit_type == "water_office",
            SurveyTask.organization_unit_uid == office_scope_uid,
        ).exists()
        context_filters.append(scoped_task)
    if project_uid:
        context_filters.append(ResultSubmission.project_uid == project_uid)
    if survey_batch_uid:
        context_filters.append(ResultSubmission.survey_batch_uid == survey_batch_uid)
    normalized_keyword = str(keyword or "").strip()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        context_filters.append(
            or_(
                ResultSubmission.result_name.ilike(pattern),
                ResultSubmission.original_filename.ilike(pattern),
                ResultSubmission.uploader_username.ilike(pattern),
            )
        )
    filters = list(context_filters)
    queue_statuses = {
        "check": ("uploaded", "inspected"),
        "review": ("preflight_passed", "reviewing"),
        "import": ("accepted",),
        "attention": ("invalid", "conflict", "rejected"),
    }
    if queue:
        filters.append(ResultSubmission.status.in_(queue_statuses[queue]))
    elif status:
        filters.append(ResultSubmission.status == status)

    total = int(
        db.scalar(select(func.count(ResultSubmission.id)).where(*filters)) or 0
    )
    rows = list(
        db.scalars(
            select(ResultSubmission)
            .where(*filters)
            .order_by(
                ResultSubmission.uploaded_at.desc(),
                ResultSubmission.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    )
    status_counts = {
        str(value): int(count)
        for value, count in db.execute(
            select(ResultSubmission.status, func.count(ResultSubmission.id))
            .where(*context_filters)
            .group_by(ResultSubmission.status)
        ).all()
    }
    summary = {
        "total": sum(status_counts.values()),
        "awaiting_check": sum(status_counts.get(value, 0) for value in {"uploaded", "inspected"}),
        "awaiting_review": sum(
            status_counts.get(value, 0) for value in {"preflight_passed", "reviewing"}
        ),
        "needs_attention": sum(
            status_counts.get(value, 0) for value in {"invalid", "conflict", "rejected"}
        ),
        "accepted": status_counts.get("accepted", 0),
        "imported": status_counts.get("imported", 0),
    }
    return rows, total, summary


async def receive_submission(
    db: Session,
    *,
    upload: UploadFile,
    uploader: User,
) -> tuple[ResultSubmission, bool]:
    ensure_storage()

    filename = Path(upload.filename or "upload.ydresult").name.strip()
    if not filename.lower().endswith(".ydresult"):
        raise ValueError("只允许上传 .ydresult 调查成果包。")

    submission_uid = uuid4().hex
    temp_path = INCOMING_DIR / f"{submission_uid}.part"

    try:
        file_sha256, file_size = await save_upload(upload, temp_path)
        inspection = inspect_result_package(temp_path)

        manifest = inspection.manifest or {}
        result = inspection.result or {}

        package_uid = (
            manifest.get("package_uid")
            if isinstance(manifest.get("package_uid"), str)
            and len(manifest.get("package_uid")) == 32
            else None
        )
        result_uid = (
            manifest.get("result_uid")
            if isinstance(manifest.get("result_uid"), str)
            and len(manifest.get("result_uid")) == 32
            else None
        )

        if package_uid:
            existing = db.scalar(
                select(ResultSubmission).where(
                    ResultSubmission.package_uid == package_uid
                )
            )
            if existing is not None:
                if existing.file_sha256 == file_sha256:
                    temp_path.unlink(missing_ok=True)
                    return existing, True
                raise DuplicatePackageConflictError(
                    "相同 package_uid 已存在，但文件 SHA-256 不一致。"
                )

        if result_uid:
            existing = db.scalar(
                select(ResultSubmission).where(
                    ResultSubmission.result_uid == result_uid
                )
            )
            if existing is not None:
                raise DuplicateResultError("相同 result_uid 的成果已经提交。")

        now = datetime.now().astimezone()
        final_dir = (
            SUBMISSIONS_DIR
            / f"{now.year:04d}"
            / f"{now.month:02d}"
            / submission_uid
        )
        final_dir.mkdir(parents=True, exist_ok=False)
        final_path = final_dir / "package.ydresult"
        shutil.move(str(temp_path), str(final_path))
        relative_path = final_path.relative_to(BACKEND_ROOT).as_posix()

        source_task_uids = result.get("source_task_uids")
        if not isinstance(source_task_uids, list):
            source_task_uids = []

        counts = result.get("counts")
        if not isinstance(counts, dict):
            counts = {}

        row = ResultSubmission(
            submission_uid=submission_uid,
            package_uid=package_uid,
            result_uid=result_uid,
            project_uid=(
                manifest.get("project_uid")
                if isinstance(manifest.get("project_uid"), str)
                and len(manifest.get("project_uid")) == 32
                else None
            ),
            survey_batch_uid=(
                manifest.get("survey_batch_uid")
                if isinstance(manifest.get("survey_batch_uid"), str)
                and len(manifest.get("survey_batch_uid")) == 32
                else None
            ),
            original_filename=filename,
            stored_relative_path=relative_path,
            file_sha256=file_sha256,
            file_size=file_size,
            package_format_version=(
                str(manifest.get("package_format_version"))
                if manifest.get("package_format_version") is not None
                else None
            ),
            desktop_app_version=(
                str(manifest.get("app_version"))
                if manifest.get("app_version") is not None
                else None
            ),
            desktop_app_version_label=(
                str(manifest.get("app_version_label"))
                if manifest.get("app_version_label") is not None
                else None
            ),
            result_name=(
                str(result.get("result_name"))[:255]
                if result.get("result_name") is not None
                else None
            ),
            source_task_uids=source_task_uids,
            submission_task_uid=(
                str(
                    result.get("submission_task_uid")
                    or manifest.get("submission_task_uid")
                )
                if (
                    result.get("submission_task_uid")
                    or manifest.get("submission_task_uid")
                )
                else None
            ),
            counts_json=counts,
            status="inspected" if inspection.valid else "invalid",
            inspection_error_count=inspection.error_count,
            inspection_issues_json=[
                item.as_dict() for item in inspection.issues
            ],
            uploader_user_uid=uploader.user_uid,
            uploader_username=uploader.username,
        )
        db.add(row)

        try:
            db.commit()
            db.refresh(row)
        except Exception:
            db.rollback()
            shutil.rmtree(final_dir, ignore_errors=True)
            raise

        return row, False

    finally:
        temp_path.unlink(missing_ok=True)
        await upload.close()


def submission_file_path(row: ResultSubmission) -> Path:
    path = (BACKEND_ROOT / row.stored_relative_path).resolve()
    root = STORAGE_ROOT.resolve()

    if path == root or root not in path.parents:
        raise RuntimeError("成果包存储路径越界。")
    if not path.is_file():
        raise FileNotFoundError("服务器上的成果包文件不存在。")
    return path
