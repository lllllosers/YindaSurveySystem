from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.central_record import CentralEngineeringAsset, CentralSurveyRecord
from app.models.online_entry import OnlineSurveyEntry
from app.models.project import Project, SurveyBatch
from app.models.result_submission import ResultSubmission
from app.models.survey_task import SurveyTask
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    SurveyBatchCreate,
    SurveyBatchUpdate,
)
from app.services.access_scope import visible_batch_ids, visible_project_ids


class DuplicateBatchCodeError(ValueError):
    pass


class ProjectHasBatchesError(ValueError):
    pass


class ProjectInUseError(ValueError):
    pass


class BatchInUseError(ValueError):
    pass


def list_projects(db: Session, office_scope_uid: str | None = None) -> list[Project]:
    query = select(Project)
    if office_scope_uid:
        query = query.where(Project.id.in_(visible_project_ids(office_scope_uid)))
    return list(
        db.scalars(
            query.order_by(
                Project.created_at.desc(),
                Project.id.desc(),
            )
        )
    )


def get_project(db: Session, project_uid: str) -> Project | None:
    return db.scalar(
        select(Project).where(Project.project_uid == project_uid)
    )


def create_project(db: Session, payload: ProjectCreate) -> Project:
    project = Project(
        name=payload.name.strip(),
        short_name=payload.short_name.strip() if payload.short_name else None,
        status=payload.status,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(
    db: Session,
    project: Project,
    payload: ProjectUpdate,
) -> Project:
    values = payload.model_dump(exclude_unset=True)

    if "name" in values and values["name"] is not None:
        values["name"] = values["name"].strip()
    if "short_name" in values and values["short_name"] is not None:
        values["short_name"] = values["short_name"].strip() or None

    for key, value in values.items():
        setattr(project, key, value)

    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project: Project) -> None:
    has_batch = db.scalar(
        select(SurveyBatch.id)
        .where(SurveyBatch.project_id == project.id)
        .limit(1)
    )
    if has_batch is not None:
        raise ProjectHasBatchesError(
            "项目下仍有调查批次，请先处理批次。"
        )

    if any((
        db.scalar(select(model.id).where(model.project_uid == project.project_uid).limit(1)) is not None
        for model in (ResultSubmission, OnlineSurveyEntry, CentralSurveyRecord, CentralEngineeringAsset)
    )):
        raise ProjectInUseError("项目已有成果包、在线记录或正式成果，不能删除；可将项目归档。")

    db.delete(project)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ProjectInUseError("项目仍被业务资料引用，不能删除；可将项目归档。") from exc


def list_batches(db: Session, project: Project, office_scope_uid: str | None = None) -> list[SurveyBatch]:
    query = select(SurveyBatch).where(SurveyBatch.project_id == project.id)
    if office_scope_uid:
        query = query.where(SurveyBatch.id.in_(visible_batch_ids(office_scope_uid)))
    return list(
        db.scalars(
            query
            .order_by(
                SurveyBatch.created_at.desc(),
                SurveyBatch.id.desc(),
            )
        )
    )


def get_batch(db: Session, survey_batch_uid: str) -> SurveyBatch | None:
    return db.scalar(
        select(SurveyBatch).where(
            SurveyBatch.survey_batch_uid == survey_batch_uid
        )
    )


def create_batch(
    db: Session,
    project: Project,
    payload: SurveyBatchCreate,
) -> SurveyBatch:
    batch = SurveyBatch(
        project_id=project.id,
        batch_name=payload.batch_name.strip(),
        batch_code=payload.batch_code.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=payload.status,
    )
    db.add(batch)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateBatchCodeError(
            "batch_code must be unique within a project"
        ) from exc

    db.refresh(batch)
    return batch


def update_batch(
    db: Session,
    batch: SurveyBatch,
    payload: SurveyBatchUpdate,
) -> SurveyBatch:
    values = payload.model_dump(exclude_unset=True)

    if "batch_name" in values and values["batch_name"] is not None:
        values["batch_name"] = values["batch_name"].strip()
    if "batch_code" in values and values["batch_code"] is not None:
        values["batch_code"] = values["batch_code"].strip()

    next_start = values.get("start_date", batch.start_date)
    next_end = values.get("end_date", batch.end_date)
    if (
        next_start is not None
        and next_end is not None
        and next_end < next_start
    ):
        raise ValueError("end_date must be on or after start_date")

    for key, value in values.items():
        setattr(batch, key, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateBatchCodeError(
            "batch_code must be unique within a project"
        ) from exc

    db.refresh(batch)
    return batch


def delete_batch(db: Session, batch: SurveyBatch) -> None:
    if any((
        db.scalar(select(model.id).where(condition).limit(1)) is not None
        for model, condition in (
            (SurveyTask, SurveyTask.survey_batch_id == batch.id),
            (ResultSubmission, ResultSubmission.survey_batch_uid == batch.survey_batch_uid),
            (OnlineSurveyEntry, OnlineSurveyEntry.survey_batch_uid == batch.survey_batch_uid),
            (CentralSurveyRecord, CentralSurveyRecord.survey_batch_uid == batch.survey_batch_uid),
        )
    )):
        raise BatchInUseError("批次已有调查任务或成果记录，不能删除；可将批次设为已结束。")
    db.delete(batch)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise BatchInUseError("批次仍被业务资料引用，不能删除；可将批次设为已结束。") from exc
