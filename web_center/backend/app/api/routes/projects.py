from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_permission
from app.db.session import get_db
from app.models.auth import User
from app.schemas.project import (
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    SurveyBatchCreate,
    SurveyBatchRead,
)
from app.services import project_service


router = APIRouter(prefix="/projects", tags=["Projects"])
DbSession = Annotated[Session, Depends(get_db)]
ProjectReader = Annotated[User, Depends(require_permission("projects.read"))]
ProjectWriter = Annotated[User, Depends(require_permission("projects.write"))]
BatchReader = Annotated[User, Depends(require_permission("batches.read"))]
BatchWriter = Annotated[User, Depends(require_permission("batches.write"))]


def require_project(db: Session, project_uid: str):
    project = project_service.get_project(db, project_uid)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.get("", response_model=list[ProjectRead])
def get_projects(_: ProjectReader, db: DbSession):
    return project_service.list_projects(db)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def post_project(payload: ProjectCreate, _: ProjectWriter, db: DbSession):
    return project_service.create_project(db, payload)


@router.get("/{project_uid}", response_model=ProjectRead)
def get_project(project_uid: str, _: ProjectReader, db: DbSession):
    return require_project(db, project_uid)


@router.patch("/{project_uid}", response_model=ProjectRead)
def patch_project(
    project_uid: str,
    payload: ProjectUpdate,
    _: ProjectWriter,
    db: DbSession,
):
    project = require_project(db, project_uid)
    return project_service.update_project(db, project, payload)


@router.delete("/{project_uid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_uid: str, _: ProjectWriter, db: DbSession):
    project = require_project(db, project_uid)
    try:
        project_service.delete_project(db, project)
    except project_service.ProjectHasBatchesError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_uid}/batches", response_model=list[SurveyBatchRead])
def get_batches(project_uid: str, _: BatchReader, db: DbSession):
    project = require_project(db, project_uid)
    return project_service.list_batches(db, project)


@router.post(
    "/{project_uid}/batches",
    response_model=SurveyBatchRead,
    status_code=status.HTTP_201_CREATED,
)
def post_batch(
    project_uid: str,
    payload: SurveyBatchCreate,
    _: BatchWriter,
    db: DbSession,
):
    project = require_project(db, project_uid)
    try:
        return project_service.create_batch(db, project, payload)
    except project_service.DuplicateBatchCodeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
