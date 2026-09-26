from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_permission
from app.db.session import get_db
from app.models.auth import User
from app.schemas.master_data import (
    CanalRead,
    CanalWrite,
    DepartmentRead,
    DepartmentWrite,
    ManagementScopeRead,
    ManagementScopeWrite,
    MasterDataSnapshot,
    MasterStatusUpdate,
    OfficeRead,
    OfficeWrite,
)
from app.services import master_data_service


router = APIRouter(prefix="/master-data", tags=["Master Data"])
MasterDataReader = Annotated[User, Depends(require_permission("master_data.read"))]
MasterDataWriter = Annotated[User, Depends(require_permission("master_data.write"))]
DbSession = Annotated[Session, Depends(get_db)]
MasterKind = Literal["departments", "offices", "canals", "scopes"]


def _snapshot_item(kind: MasterKind, uid: str):
    snapshot = master_data_service.get_snapshot()
    items = {
        "departments": snapshot.departments,
        "offices": snapshot.offices,
        "canals": snapshot.canals,
        "scopes": snapshot.management_scopes,
    }[kind]
    return next(item for item in items if item.stable_uid == uid)


def _bad_request(exc: ValueError):
    code = 409 if isinstance(exc, master_data_service.MasterDataInUseError) else 400
    raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.get("/snapshot", response_model=MasterDataSnapshot)
def get_master_data_snapshot(_: MasterDataReader) -> MasterDataSnapshot:
    return master_data_service.get_snapshot()


@router.get("/export")
def export_master_data(_: MasterDataReader) -> Response:
    payload = master_data_service.get_snapshot().model_dump_json(indent=2)
    return Response(
        content="\ufeff" + payload,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="yinda-master-data.json"'},
    )


@router.post("/departments", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def post_department(payload: DepartmentWrite, request: Request, user: MasterDataWriter, db: DbSession):
    try: row = master_data_service.create_department(db, payload, user.username)
    except ValueError as exc: _bad_request(exc)
    request.state.audit_summary = "新增管理处基础资料"
    request.state.audit_details = {"stable_uid": row.stable_uid, "name": row.name}
    return _snapshot_item("departments", row.stable_uid)


@router.put("/departments/{uid}", response_model=DepartmentRead)
def put_department(uid: str, payload: DepartmentWrite, request: Request, user: MasterDataWriter, db: DbSession):
    try: row = master_data_service.update_department(db, uid, payload, user.username)
    except ValueError as exc: _bad_request(exc)
    request.state.audit_summary = "修改管理处基础资料"
    request.state.audit_details = {"stable_uid": uid, "name": row.name}
    return _snapshot_item("departments", uid)


@router.post("/offices", response_model=OfficeRead, status_code=status.HTTP_201_CREATED)
def post_office(payload: OfficeWrite, request: Request, user: MasterDataWriter, db: DbSession):
    try: row = master_data_service.create_office(db, payload, user.username)
    except ValueError as exc: _bad_request(exc)
    request.state.audit_summary = "新增管理所基础资料"
    request.state.audit_details = {"stable_uid": row.stable_uid, "name": row.name}
    return _snapshot_item("offices", row.stable_uid)


@router.put("/offices/{uid}", response_model=OfficeRead)
def put_office(uid: str, payload: OfficeWrite, request: Request, user: MasterDataWriter, db: DbSession):
    try: row = master_data_service.update_office(db, uid, payload, user.username)
    except ValueError as exc: _bad_request(exc)
    request.state.audit_summary = "修改管理所基础资料"
    request.state.audit_details = {"stable_uid": uid, "name": row.name}
    return _snapshot_item("offices", uid)


@router.post("/canals", response_model=CanalRead, status_code=status.HTTP_201_CREATED)
def post_canal(payload: CanalWrite, request: Request, user: MasterDataWriter, db: DbSession):
    try: row = master_data_service.create_canal(db, payload, user.username)
    except ValueError as exc: _bad_request(exc)
    request.state.audit_summary = "新增渠道基础资料"
    request.state.audit_details = {"stable_uid": row.stable_uid, "name": row.name}
    return _snapshot_item("canals", row.stable_uid)


@router.put("/canals/{uid}", response_model=CanalRead)
def put_canal(uid: str, payload: CanalWrite, request: Request, user: MasterDataWriter, db: DbSession):
    try: row = master_data_service.update_canal(db, uid, payload, user.username)
    except ValueError as exc: _bad_request(exc)
    request.state.audit_summary = "修改渠道基础资料"
    request.state.audit_details = {"stable_uid": uid, "name": row.name}
    return _snapshot_item("canals", uid)


@router.post("/scopes", response_model=ManagementScopeRead, status_code=status.HTTP_201_CREATED)
def post_scope(payload: ManagementScopeWrite, request: Request, user: MasterDataWriter, db: DbSession):
    try: row = master_data_service.create_scope(db, payload, user.username)
    except ValueError as exc: _bad_request(exc)
    request.state.audit_summary = "新增渠道分管范围"
    request.state.audit_details = {"stable_uid": row.stable_uid, "canal_uid": row.canal_uid}
    return _snapshot_item("scopes", row.stable_uid)


@router.put("/scopes/{uid}", response_model=ManagementScopeRead)
def put_scope(uid: str, payload: ManagementScopeWrite, request: Request, user: MasterDataWriter, db: DbSession):
    try: row = master_data_service.update_scope(db, uid, payload, user.username)
    except ValueError as exc: _bad_request(exc)
    request.state.audit_summary = "修改渠道分管范围"
    request.state.audit_details = {"stable_uid": uid, "canal_uid": row.canal_uid}
    return _snapshot_item("scopes", uid)


@router.post("/{kind}/{uid}/status")
def change_status(kind: MasterKind, uid: str, payload: MasterStatusUpdate, request: Request, user: MasterDataWriter, db: DbSession):
    try: master_data_service.set_status(db, kind, uid, payload.status, user.username)
    except ValueError as exc: _bad_request(exc)
    request.state.audit_summary = "启用基础资料" if payload.status == "active" else "停用基础资料"
    request.state.audit_details = {"kind": kind, "stable_uid": uid, "status": payload.status}
    return _snapshot_item(kind, uid)


@router.delete("/{kind}/{uid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_master_item(kind: MasterKind, uid: str, request: Request, user: MasterDataWriter, db: DbSession):
    try: master_data_service.delete_item(db, kind, uid, user.username)
    except ValueError as exc: _bad_request(exc)
    request.state.audit_summary = "删除未使用的基础资料"
    request.state.audit_details = {"kind": kind, "stable_uid": uid}
    return Response(status_code=status.HTTP_204_NO_CONTENT)
