from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_permission
from app.db.session import get_db
from app.db.session import engine
from app.models.auth import User
from app.models.central_record import CentralSurveyRecord
from app.models.online_entry import OnlineSurveyEntry
from app.models.project import Project, SurveyBatch
from app.models.result_submission import ResultSubmission
from app.models.survey_task import SurveyTask
from app.services.master_data_service import get_snapshot
from app.services import access_scope


router = APIRouter(tags=["System"])
API_GENERATION = "2026.09.27-deployment-cleanup-v6"
OverviewReader = Annotated[
    User,
    Depends(require_permission("projects.read")),
]
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/health")
def health_check(request: Request) -> dict[str, str]:
    if request.app.state.settings.app_env == "production":
        return {"status": "ok"}
    return {
        "status": "ok",
        "service": "yinda-web-center-api",
        "api_generation": API_GENERATION,
    }


@router.get("/health/database")
def database_health_check() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).one()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database connection is unavailable.",
        ) from exc

    return {"status": "ok"}


@router.get("/overview")
def overview(user: OverviewReader, db: DbSession) -> dict:
    scope = access_scope.office_scope(user)
    package_scope = select(SurveyTask.id).where(
        SurveyTask.task_uid == ResultSubmission.submission_task_uid,
        SurveyTask.target_unit_type == "water_office",
        SurveyTask.organization_unit_uid == scope,
    ).exists() if scope else None
    snapshot = get_snapshot()
    master_data = snapshot.summary
    active_scope_canal_keys = {
        item.canal_master_key
        for item in snapshot.management_scopes
        if item.status == "active"
    }
    unassigned_backbone_canal_count = sum(
        1
        for item in snapshot.canals
        if item.status == "active"
        and item.canal_level in {"01", "02"}
        and item.master_key not in active_scope_canal_keys
    )

    pending_package_review_count = int(
        db.scalar(
            select(func.count())
            .select_from(ResultSubmission)
            .where(ResultSubmission.status.in_(("preflight_passed", "reviewing")))
            .where(package_scope if package_scope is not None else True)
        ) or 0
    )
    pending_online_review_count = int(
        db.scalar(
            select(func.count())
            .select_from(OnlineSurveyEntry)
            .where(OnlineSurveyEntry.status == "submitted")
            .where(OnlineSurveyEntry.organization_unit_uid == scope if scope else True)
        ) or 0
    )
    pending_user_count = 0
    if user.role == "admin":
        pending_user_count = int(
            db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.is_approved.is_(False))
            ) or 0
        )

    return {
        "product_version": "V1.2.0",
        "web_stage": "中心业务版",
        "task_protocol": ".ydtask V3",
        "result_protocol": ".ydresult 2.2",
        "project_count": int(
            db.scalar(select(func.count()).select_from(Project).where(Project.id.in_(access_scope.visible_project_ids(scope)) if scope else True)) or 0
        ),
        "active_batch_count": int(
            db.scalar(
                select(func.count())
                .select_from(SurveyBatch)
                .where(SurveyBatch.status == "active")
                .where(SurveyBatch.id.in_(access_scope.visible_batch_ids(scope)) if scope else True)
            )
            or 0
        ),
        "result_submission_count": int(
            db.scalar(select(func.count()).select_from(ResultSubmission).where(package_scope if package_scope is not None else True)) or 0
        ),
        "survey_task_count": int(
            db.scalar(select(func.count()).select_from(SurveyTask).where(SurveyTask.target_unit_type == "water_office", SurveyTask.organization_unit_uid == scope) if scope else select(func.count()).select_from(SurveyTask)) or 0
        ),
        "central_record_count": int(
            db.scalar(select(func.count()).select_from(CentralSurveyRecord).where(CentralSurveyRecord.organization_unit_uid == scope if scope else True)) or 0
        ),
        "pending_review_count": pending_package_review_count + pending_online_review_count,
        "pending_package_review_count": pending_package_review_count,
        "pending_online_review_count": pending_online_review_count,
        "pending_user_count": pending_user_count,
        "active_user_count": int(
            db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.is_active.is_(True))
            )
            or 0
        ),
        "official_department_count": master_data.department_count,
        "official_office_count": master_data.office_count,
        "official_canal_count": master_data.canal_count,
        "official_scope_count": master_data.management_scope_count,
        "unassigned_backbone_canal_count": unassigned_backbone_canal_count,
        "master_data_version": master_data.master_data_version,
    }
