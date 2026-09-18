from fastapi import APIRouter

from app.api.routes.audit import router as audit_router

from app.api.routes.auth import router as auth_router
from app.api.routes.projects import router as projects_router
from app.api.routes.survey_batches import router as survey_batches_router
from app.api.routes.system import router as system_router
from app.api.routes.users import router as users_router

api_router = APIRouter()
api_router.include_router(audit_router)
api_router.include_router(system_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(projects_router)
api_router.include_router(survey_batches_router)
