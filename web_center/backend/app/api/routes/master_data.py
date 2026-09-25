from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import require_permission
from app.models.auth import User
from app.schemas.master_data import MasterDataSnapshot
from app.services.master_data_service import get_snapshot


router = APIRouter(prefix="/master-data", tags=["Master Data"])
MasterDataReader = Annotated[
    User,
    Depends(require_permission("master_data.read")),
]


@router.get("/snapshot", response_model=MasterDataSnapshot)
def get_master_data_snapshot(_: MasterDataReader) -> MasterDataSnapshot:
    return get_snapshot()
