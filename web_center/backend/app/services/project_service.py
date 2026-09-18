from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.project import Project, SurveyBatch
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    SurveyBatchCreate,
    SurveyBatchUpdate,
)


class DuplicateBatchCodeError(ValueError):
    pass


class ProjectHasBatchesError(ValueError):
    pass


def list_projects(db: Session) -> list[Project]:
    return list(
        db.scalars(
            select(Project).order_by(
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
            "Project cannot be deleted while survey batches exist."
        )

    db.delete(project)
    db.commit()


def list_batches(db: Session, project: Project) -> list[SurveyBatch]:
    return list(
        db.scalars(
            select(SurveyBatch)
            .where(SurveyBatch.project_id == project.id)
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
    db.delete(batch)
    db.commit()
