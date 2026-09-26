from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
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


router = APIRouter(tags=["System"])
API_GENERATION = "2026.09.26-task-handover-v3"
OverviewReader = Annotated[
    User,
    Depends(require_permission("projects.read")),
]
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "yinda-web-center-api",
        "api_generation": API_GENERATION,
    }


@router.get("/health/database")
def database_health_check() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            database_name, database_user = connection.execute(
                text("SELECT current_database(), current_user")
            ).one()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database connection is unavailable.",
        ) from exc

    return {
        "status": "ok",
        "database": str(database_name),
        "user": str(database_user),
        "engine": "postgresql",
    }


@router.get("/overview")
def overview(_: OverviewReader, db: DbSession) -> dict:
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

    return {
        "product_version": "V1.2.0",
        "web_stage": "中心业务版",
        "task_protocol": ".ydtask V3",
        "result_protocol": ".ydresult 2.2",
        "project_count": int(
            db.scalar(select(func.count()).select_from(Project)) or 0
        ),
        "active_batch_count": int(
            db.scalar(
                select(func.count())
                .select_from(SurveyBatch)
                .where(SurveyBatch.status == "active")
            )
            or 0
        ),
        "result_submission_count": int(
            db.scalar(select(func.count()).select_from(ResultSubmission)) or 0
        ),
        "survey_task_count": int(
            db.scalar(select(func.count()).select_from(SurveyTask)) or 0
        ),
        "central_record_count": int(
            db.scalar(select(func.count()).select_from(CentralSurveyRecord)) or 0
        ),
        "pending_review_count": int(
            db.scalar(
                select(func.count())
                .select_from(ResultSubmission)
                .where(ResultSubmission.status == "preflight_passed")
            )
            or 0
        ) + int(
            db.scalar(
                select(func.count())
                .select_from(OnlineSurveyEntry)
                .where(OnlineSurveyEntry.status == "submitted")
            )
            or 0
        ),
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
