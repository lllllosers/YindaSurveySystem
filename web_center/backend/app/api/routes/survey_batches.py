from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.project import SurveyBatchRead, SurveyBatchUpdate
from app.services import project_service


router = APIRouter(prefix="/survey-batches", tags=["Survey Batches"])
DbSession = Annotated[Session, Depends(get_db)]


def require_batch(db: Session, survey_batch_uid: str):
    batch = project_service.get_batch(db, survey_batch_uid)
    if batch is None:
        raise HTTPException(status_code=404, detail="Survey batch not found.")
    return batch


@router.patch(
    "/{survey_batch_uid}",
    response_model=SurveyBatchRead,
)
def patch_batch(
    survey_batch_uid: str,
    payload: SurveyBatchUpdate,
    db: DbSession,
):
    batch = require_batch(db, survey_batch_uid)

    try:
        return project_service.update_batch(db, batch, payload)
    except project_service.DuplicateBatchCodeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete(
    "/{survey_batch_uid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_batch(survey_batch_uid: str, db: DbSession):
    batch = require_batch(db, survey_batch_uid)
    project_service.delete_batch(db, batch)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
