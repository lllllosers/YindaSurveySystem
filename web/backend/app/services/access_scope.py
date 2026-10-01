"""Optional office-level read and review boundary for non-management roles."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.result_submission import ResultSubmission
from app.models.survey_task import SurveyTask


def office_scope(user: User) -> str | None:
    return user.office_scope_uid if user.role in {"reviewer", "viewer"} else None


def require_office(user: User, office_uid: str) -> None:
    scope = office_scope(user)
    if scope and scope != office_uid:
        raise HTTPException(status_code=404, detail="记录不存在或不属于当前授权单位。")


def require_task(user: User, task: SurveyTask) -> None:
    scope = office_scope(user)
    if scope and (task.target_unit_type != "water_office" or task.organization_unit_uid != scope):
        raise HTTPException(status_code=404, detail="任务不存在或不属于当前授权单位。")


def require_submission(db: Session, user: User, row: ResultSubmission) -> None:
    scope = office_scope(user)
    if not scope:
        return
    task = db.scalar(select(SurveyTask).where(SurveyTask.task_uid == row.submission_task_uid))
    if task is None or task.target_unit_type != "water_office" or task.organization_unit_uid != scope:
        raise HTTPException(status_code=404, detail="成果包不存在或不属于当前授权单位。")


def visible_project_ids(office_uid: str):
    return select(SurveyTask.project_id).where(
        SurveyTask.target_unit_type == "water_office",
        SurveyTask.organization_unit_uid == office_uid,
    )


def visible_batch_ids(office_uid: str):
    return select(SurveyTask.survey_batch_id).where(
        SurveyTask.target_unit_type == "water_office",
        SurveyTask.organization_unit_uid == office_uid,
    )


def require_project(db: Session, user: User, project_id: int) -> None:
    scope = office_scope(user)
    if scope and db.scalar(
        select(SurveyTask.id).where(
            SurveyTask.project_id == project_id,
            SurveyTask.target_unit_type == "water_office",
            SurveyTask.organization_unit_uid == scope,
        ).limit(1)
    ) is None:
        raise HTTPException(status_code=404, detail="项目不存在或不属于当前授权单位。")
