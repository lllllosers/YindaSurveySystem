from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import sys
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.central_record import CentralSurveyRecord
from app.models.master_data import (
    MasterCanal,
    MasterDataState,
    MasterDepartment,
    MasterManagementScope,
    MasterOffice,
)
from app.models.online_entry import OnlineSurveyEntry
from app.models.survey_task import SurveyTask
from app.schemas.master_data import (
    CanalRead,
    CanalWrite,
    DepartmentRead,
    DepartmentWrite,
    ManagementScopeRead,
    ManagementScopeWrite,
    MasterDataSnapshot,
    MasterDataSummary,
    OfficeRead,
    OfficeWrite,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = REPOSITORY_ROOT / "shared" / "master_data" / "official_master_contract.json"
SUPPORTED_CONTRACT_SCHEMA_VERSION = "1.0"
ALLOWED_RANGE_MODES = {"whole", "segment_known", "segment_unknown"}
DESKTOP_SRC = REPOSITORY_ROOT / "src"
if str(DESKTOP_SRC) not in sys.path:
    sys.path.insert(0, str(DESKTOP_SRC))

from services.stake import parse_stake  # noqa: E402


class MasterDataInUseError(ValueError):
    pass


def deterministic_master_uid(identity_namespace: str, entity_kind: str, master_key: str) -> str:
    payload = f"{identity_namespace}:{entity_kind}:{master_key}".encode("utf-8")
    return sha256(payload).hexdigest()[:32]


def _require_text(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"正式主数据契约字段 {key!r} 必须是非空字符串。")
    return value


def _require_records(data: dict, key: str) -> list[dict]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RuntimeError(f"正式主数据契约字段 {key!r} 必须是对象数组。")
    return value


def _master_key_map(records: list[dict], label: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for record in records:
        key = record.get("master_key")
        if not isinstance(key, str) or not key.strip():
            raise RuntimeError(f"{label}记录缺少有效 master_key。")
        if key in result:
            raise RuntimeError(f"{label}存在重复 master_key：{key}。")
        result[key] = record
    return result


def _validate_contract(data: dict) -> None:
    if _require_text(data, "contract_schema_version") != SUPPORTED_CONTRACT_SCHEMA_VERSION:
        raise RuntimeError("不支持的正式主数据契约版本。")
    for key in ("identity_namespace", "master_data_version", "master_data_source", "management_scope_version", "management_scope_source"):
        _require_text(data, key)
    departments = _require_records(data, "departments")
    offices = _require_records(data, "offices")
    canals = _require_records(data, "canals")
    scopes = _require_records(data, "management_scopes")
    department_map = _master_key_map(departments, "管理处")
    office_map = _master_key_map(offices, "管理所")
    canal_map = _master_key_map(canals, "渠道")
    _master_key_map(scopes, "渠道管理范围")
    if any(item.get("parent_master_key") not in department_map for item in offices):
        raise RuntimeError("管理所引用了不存在的管理处。")
    if any(item.get("parent_master_key") is not None and item.get("parent_master_key") not in canal_map for item in canals):
        raise RuntimeError("渠道引用了不存在的上级渠道。")
    for scope in scopes:
        if scope.get("canal_master_key") not in canal_map or scope.get("organization_master_key") not in office_map:
            raise RuntimeError("管理范围引用了不存在的渠道或管理所。")
        if scope.get("range_mode") not in ALLOWED_RANGE_MODES:
            raise RuntimeError("管理范围类型无效。")


@lru_cache(maxsize=1)
def load_contract() -> tuple[dict, str]:
    try:
        raw = CONTRACT_PATH.read_bytes()
        data = json.loads(raw.decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("正式主数据初始化文件读取失败。") from exc
    if not isinstance(data, dict):
        raise RuntimeError("正式主数据初始化文件格式无效。")
    _validate_contract(data)
    return data, sha256(raw).hexdigest()


def ensure_seeded(db: Session) -> None:
    if db.get(MasterDataState, 1) is not None:
        return
    data, _ = load_contract()
    namespace = str(data["identity_namespace"])
    department_uids: dict[str, str] = {}
    office_uids: dict[str, str] = {}
    canal_uids: dict[str, str] = {}
    for item in data["departments"]:
        uid = deterministic_master_uid(namespace, "organization", str(item["master_key"]))
        department_uids[str(item["master_key"])] = uid
        db.add(MasterDepartment(stable_uid=uid, master_key=str(item["master_key"]), name=str(item["name"]), business_code=str(item["business_code"]), sort_order=int(item.get("sort_order", 0)), status="active", description=item.get("description")))
    for item in data["offices"]:
        uid = deterministic_master_uid(namespace, "organization", str(item["master_key"]))
        office_uids[str(item["master_key"])] = uid
        db.add(MasterOffice(stable_uid=uid, master_key=str(item["master_key"]), parent_department_uid=department_uids[str(item["parent_master_key"])], name=str(item["name"]), business_code=str(item["business_code"]), sort_order=int(item.get("sort_order", 0)), status="active", description=item.get("description")))
    for item in data["canals"]:
        canal_uids[str(item["master_key"])] = deterministic_master_uid(namespace, "canal", str(item["master_key"]))
    for item in data["canals"]:
        parent_key = item.get("parent_master_key")
        db.add(MasterCanal(stable_uid=canal_uids[str(item["master_key"])], master_key=str(item["master_key"]), parent_canal_uid=canal_uids[str(parent_key)] if parent_key else None, name=str(item["name"]), canal_level=str(item["canal_level"]), sort_order=int(item.get("sort_order", 0)), status="active", description=item.get("description")))
    for item in data["management_scopes"]:
        db.add(MasterManagementScope(stable_uid=deterministic_master_uid(namespace, "canal_management_scope", str(item["master_key"])), master_key=str(item["master_key"]), canal_uid=canal_uids[str(item["canal_master_key"])], organization_unit_uid=office_uids[str(item["organization_master_key"])], range_mode=str(item["range_mode"]), start_stake_text=item.get("start_stake_text"), start_stake_value=item.get("start_stake_value"), end_stake_text=item.get("end_stake_text"), end_stake_value=item.get("end_stake_value"), sort_order=int(item.get("sort_order", 0)), status=str(item.get("status", "active")), description=item.get("description")))
    db.add(MasterDataState(id=1, revision_no=1, base_version=str(data["master_data_version"]), source_description=str(data["master_data_source"]), updated_by_username="系统初始化"))
    db.commit()


def _all(db: Session):
    ensure_seeded(db)
    departments = list(db.scalars(select(MasterDepartment).order_by(MasterDepartment.sort_order, MasterDepartment.id)))
    offices = list(db.scalars(select(MasterOffice).order_by(MasterOffice.sort_order, MasterOffice.id)))
    canals = list(db.scalars(select(MasterCanal).order_by(MasterCanal.sort_order, MasterCanal.id)))
    scopes = list(db.scalars(select(MasterManagementScope).order_by(MasterManagementScope.sort_order, MasterManagementScope.id)))
    return departments, offices, canals, scopes


def get_snapshot() -> MasterDataSnapshot:
    with SessionLocal() as db:
        departments, offices, canals, scopes = _all(db)
        state = db.get(MasterDataState, 1)
        assert state is not None
        department_by_uid = {item.stable_uid: item for item in departments}
        office_by_uid = {item.stable_uid: item for item in offices}
        canal_by_uid = {item.stable_uid: item for item in canals}
        payload = {
            "revision": state.revision_no,
            "departments": [{"uid": x.stable_uid, "name": x.name, "code": x.business_code, "status": x.status, "order": x.sort_order, "description": x.description} for x in departments],
            "offices": [{"uid": x.stable_uid, "parent": x.parent_department_uid, "name": x.name, "code": x.business_code, "status": x.status, "order": x.sort_order, "description": x.description} for x in offices],
            "canals": [{"uid": x.stable_uid, "parent": x.parent_canal_uid, "name": x.name, "level": x.canal_level, "status": x.status, "order": x.sort_order, "description": x.description} for x in canals],
            "scopes": [{"uid": x.stable_uid, "canal": x.canal_uid, "office": x.organization_unit_uid, "mode": x.range_mode, "start": x.start_stake_value, "end": x.end_stake_value, "status": x.status, "order": x.sort_order, "description": x.description} for x in scopes],
        }
        digest = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return MasterDataSnapshot(
            summary=MasterDataSummary(contract_schema_version="2.0", master_data_version=f"中心正式版 R{state.revision_no}", management_scope_version=f"中心正式版 R{state.revision_no}", source_description="中心基础资料库（首次数据来自正式资料基线）", contract_sha256=digest, department_count=len(departments), office_count=len(offices), canal_count=len(canals), management_scope_count=len(scopes)),
            departments=[DepartmentRead(master_key=x.master_key, stable_uid=x.stable_uid, name=x.name, business_code=x.business_code, sort_order=x.sort_order, description=x.description, status=x.status) for x in departments],
            offices=[OfficeRead(master_key=x.master_key, stable_uid=x.stable_uid, parent_master_key=department_by_uid[x.parent_department_uid].master_key, parent_name=department_by_uid[x.parent_department_uid].name, name=x.name, business_code=x.business_code, sort_order=x.sort_order, description=x.description, status=x.status) for x in offices],
            canals=[CanalRead(master_key=x.master_key, stable_uid=x.stable_uid, name=x.name, canal_level=x.canal_level, parent_master_key=canal_by_uid[x.parent_canal_uid].master_key if x.parent_canal_uid else None, parent_name=canal_by_uid[x.parent_canal_uid].name if x.parent_canal_uid else None, sort_order=x.sort_order, description=x.description, status=x.status) for x in canals],
            management_scopes=[ManagementScopeRead(master_key=x.master_key, stable_uid=x.stable_uid, canal_master_key=canal_by_uid[x.canal_uid].master_key, canal_name=canal_by_uid[x.canal_uid].name, organization_master_key=office_by_uid[x.organization_unit_uid].master_key, organization_name=office_by_uid[x.organization_unit_uid].name, range_mode=x.range_mode, start_stake_text=x.start_stake_text, start_stake_value=x.start_stake_value, end_stake_text=x.end_stake_text, end_stake_value=x.end_stake_value, sort_order=x.sort_order, status=x.status, description=x.description) for x in scopes],
        )


def _bump(db: Session, username: str) -> None:
    state = db.get(MasterDataState, 1)
    assert state is not None
    state.revision_no += 1
    state.updated_by_username = username


def _new_key(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12].upper()}"


def _require(db: Session, model, uid: str, label: str):
    ensure_seeded(db)
    row = db.scalar(select(model).where(model.stable_uid == uid))
    if row is None:
        raise ValueError(f"{label}不存在。")
    return row


def _duplicate(db: Session, model, *, name: str, exclude_uid: str | None = None, extra=None) -> None:
    stmt = select(model).where(func.lower(model.name) == name.lower())
    if exclude_uid:
        stmt = stmt.where(model.stable_uid != exclude_uid)
    if extra is not None:
        stmt = stmt.where(extra)
    if db.scalar(stmt) is not None:
        raise ValueError("已存在同名基础资料。")


def create_department(db: Session, payload: DepartmentWrite, username: str) -> MasterDepartment:
    ensure_seeded(db)
    _duplicate(db, MasterDepartment, name=payload.name)
    if db.scalar(select(MasterDepartment).where(MasterDepartment.business_code == payload.business_code)):
        raise ValueError("管理处业务编码已存在。")
    row = MasterDepartment(master_key=_new_key("ORG-D"), **payload.model_dump())
    db.add(row); _bump(db, username); db.commit(); db.refresh(row); return row


def update_department(db: Session, uid: str, payload: DepartmentWrite, username: str) -> MasterDepartment:
    row = _require(db, MasterDepartment, uid, "管理处")
    _duplicate(db, MasterDepartment, name=payload.name, exclude_uid=uid)
    if db.scalar(select(MasterDepartment).where(MasterDepartment.business_code == payload.business_code, MasterDepartment.stable_uid != uid)):
        raise ValueError("管理处业务编码已存在。")
    for key, value in payload.model_dump().items(): setattr(row, key, value)
    _bump(db, username); db.commit(); db.refresh(row); return row


def create_office(db: Session, payload: OfficeWrite, username: str) -> MasterOffice:
    parent = _require(db, MasterDepartment, payload.parent_department_uid, "所属管理处")
    if parent.status != "active": raise ValueError("不能在已停用的管理处下新增管理所。")
    _duplicate(db, MasterOffice, name=payload.name, extra=MasterOffice.parent_department_uid == parent.stable_uid)
    row = MasterOffice(master_key=_new_key("ORG-O"), **payload.model_dump())
    db.add(row); _bump(db, username); db.commit(); db.refresh(row); return row


def update_office(db: Session, uid: str, payload: OfficeWrite, username: str) -> MasterOffice:
    row = _require(db, MasterOffice, uid, "管理所")
    parent = _require(db, MasterDepartment, payload.parent_department_uid, "所属管理处")
    if parent.status != "active": raise ValueError("所属管理处已停用。")
    _duplicate(db, MasterOffice, name=payload.name, exclude_uid=uid, extra=MasterOffice.parent_department_uid == parent.stable_uid)
    for key, value in payload.model_dump().items(): setattr(row, key, value)
    _bump(db, username); db.commit(); db.refresh(row); return row


def _assert_no_canal_cycle(db: Session, uid: str | None, parent_uid: str | None) -> None:
    current = parent_uid
    visited = set()
    while current:
        if current == uid: raise ValueError("上级渠道不能形成循环层级。")
        if current in visited: raise ValueError("现有渠道层级存在循环。")
        visited.add(current)
        current = _require(db, MasterCanal, current, "上级渠道").parent_canal_uid


def create_canal(db: Session, payload: CanalWrite, username: str) -> MasterCanal:
    ensure_seeded(db)
    if payload.parent_canal_uid:
        parent = _require(db, MasterCanal, payload.parent_canal_uid, "上级渠道")
        if parent.status != "active": raise ValueError("不能在已停用渠道下新增下级渠道。")
    _duplicate(db, MasterCanal, name=payload.name, extra=MasterCanal.parent_canal_uid == payload.parent_canal_uid)
    row = MasterCanal(master_key=_new_key("CANAL"), **payload.model_dump())
    db.add(row); _bump(db, username); db.commit(); db.refresh(row); return row


def update_canal(db: Session, uid: str, payload: CanalWrite, username: str) -> MasterCanal:
    row = _require(db, MasterCanal, uid, "渠道")
    if payload.parent_canal_uid:
        parent = _require(db, MasterCanal, payload.parent_canal_uid, "上级渠道")
        if parent.status != "active": raise ValueError("上级渠道已停用。")
    _assert_no_canal_cycle(db, uid, payload.parent_canal_uid)
    _duplicate(db, MasterCanal, name=payload.name, exclude_uid=uid, extra=MasterCanal.parent_canal_uid == payload.parent_canal_uid)
    for key, value in payload.model_dump().items(): setattr(row, key, value)
    _bump(db, username); db.commit(); db.refresh(row); return row


def _scope_values(payload: ManagementScopeWrite) -> tuple[str | None, float | None, str | None, float | None]:
    if payload.range_mode != "segment_known": return None, None, None, None
    try:
        start_text, start_value = parse_stake(payload.start_stake_text or "")
        end_text, end_value = parse_stake(payload.end_stake_text or "")
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    if start_value is None or end_value is None or start_value >= end_value:
        raise ValueError("终止桩号必须大于起始桩号。")
    return start_text, start_value, end_text, end_value


def _validate_scope_conflicts(db: Session, canal_uid: str, mode: str, start: float | None, end: float | None, exclude_uid: str | None = None) -> None:
    stmt = select(MasterManagementScope).where(MasterManagementScope.canal_uid == canal_uid, MasterManagementScope.status == "active")
    if exclude_uid: stmt = stmt.where(MasterManagementScope.stable_uid != exclude_uid)
    rows = list(db.scalars(stmt))
    if mode == "whole" and rows: raise ValueError("该渠道已有分管范围，不能再设置全渠管理。")
    if any(x.range_mode == "whole" for x in rows): raise ValueError("该渠道已设置全渠管理，不能再增加其他分段。")
    if mode == "segment_known":
        for row in rows:
            if row.range_mode == "segment_known" and start is not None and end is not None and row.start_stake_value is not None and row.end_stake_value is not None and start < row.end_stake_value and end > row.start_stake_value:
                raise ValueError(f"该区间与现有分管段“{row.start_stake_text}—{row.end_stake_text}”重叠。")


def create_scope(db: Session, payload: ManagementScopeWrite, username: str) -> MasterManagementScope:
    canal = _require(db, MasterCanal, payload.canal_uid, "渠道")
    office = _require(db, MasterOffice, payload.organization_unit_uid, "管理所")
    if canal.status != "active" or office.status != "active": raise ValueError("只能为启用的渠道和管理所设置分管范围。")
    start_text, start_value, end_text, end_value = _scope_values(payload)
    _validate_scope_conflicts(db, canal.stable_uid, payload.range_mode, start_value, end_value)
    data = payload.model_dump(exclude={"start_stake_text", "end_stake_text"})
    row = MasterManagementScope(master_key=_new_key("CMS"), **data, start_stake_text=start_text, start_stake_value=start_value, end_stake_text=end_text, end_stake_value=end_value)
    db.add(row); _bump(db, username); db.commit(); db.refresh(row); return row


def update_scope(db: Session, uid: str, payload: ManagementScopeWrite, username: str) -> MasterManagementScope:
    row = _require(db, MasterManagementScope, uid, "分管范围")
    canal = _require(db, MasterCanal, payload.canal_uid, "渠道")
    office = _require(db, MasterOffice, payload.organization_unit_uid, "管理所")
    if canal.status != "active" or office.status != "active": raise ValueError("只能选择启用的渠道和管理所。")
    start_text, start_value, end_text, end_value = _scope_values(payload)
    _validate_scope_conflicts(db, canal.stable_uid, payload.range_mode, start_value, end_value, uid)
    for key, value in payload.model_dump(exclude={"start_stake_text", "end_stake_text"}).items(): setattr(row, key, value)
    row.start_stake_text, row.start_stake_value, row.end_stake_text, row.end_stake_value = start_text, start_value, end_text, end_value
    _bump(db, username); db.commit(); db.refresh(row); return row


MODEL_BY_KIND = {"departments": MasterDepartment, "offices": MasterOffice, "canals": MasterCanal, "scopes": MasterManagementScope}


def set_status(db: Session, kind: str, uid: str, status: str, username: str):
    row = _require(db, MODEL_BY_KIND[kind], uid, "基础资料")
    if row.status == status: return row
    if status == "inactive":
        if kind == "departments" and db.scalar(select(func.count()).select_from(MasterOffice).where(MasterOffice.parent_department_uid == uid, MasterOffice.status == "active")):
            raise ValueError("请先停用该管理处下仍在使用的管理所。")
        if kind == "offices" and db.scalar(select(func.count()).select_from(MasterManagementScope).where(MasterManagementScope.organization_unit_uid == uid, MasterManagementScope.status == "active")):
            raise ValueError("请先停用该管理所仍在使用的分管范围。")
        if kind == "canals" and (db.scalar(select(func.count()).select_from(MasterCanal).where(MasterCanal.parent_canal_uid == uid, MasterCanal.status == "active")) or db.scalar(select(func.count()).select_from(MasterManagementScope).where(MasterManagementScope.canal_uid == uid, MasterManagementScope.status == "active"))):
            raise ValueError("请先停用下级渠道和该渠道的分管范围。")
    else:
        if kind == "offices" and _require(db, MasterDepartment, row.parent_department_uid, "所属管理处").status != "active": raise ValueError("请先启用所属管理处。")
        if kind == "canals" and row.parent_canal_uid and _require(db, MasterCanal, row.parent_canal_uid, "上级渠道").status != "active": raise ValueError("请先启用上级渠道。")
        if kind == "scopes":
            if _require(db, MasterCanal, row.canal_uid, "渠道").status != "active" or _require(db, MasterOffice, row.organization_unit_uid, "管理所").status != "active": raise ValueError("请先启用关联的渠道和管理所。")
            _validate_scope_conflicts(db, row.canal_uid, row.range_mode, row.start_stake_value, row.end_stake_value, uid)
    row.status = status; _bump(db, username); db.commit(); db.refresh(row); return row


def delete_item(db: Session, kind: str, uid: str, username: str) -> None:
    row = _require(db, MODEL_BY_KIND[kind], uid, "基础资料")
    if row.status != "inactive": raise MasterDataInUseError("请先停用该基础资料，再执行删除。")
    reasons: list[str] = []
    if kind == "departments":
        if db.scalar(select(func.count()).select_from(MasterOffice).where(MasterOffice.parent_department_uid == uid)): reasons.append("仍有关联管理所")
        if db.scalar(select(func.count()).select_from(SurveyTask).where(SurveyTask.department_uid == uid)): reasons.append("已被调查任务使用")
    elif kind == "offices":
        if db.scalar(select(func.count()).select_from(MasterManagementScope).where(MasterManagementScope.organization_unit_uid == uid)): reasons.append("仍有关联分管范围")
        if db.scalar(select(func.count()).select_from(SurveyTask).where(SurveyTask.organization_unit_uid == uid)): reasons.append("已被调查任务使用")
        if db.scalar(select(func.count()).select_from(CentralSurveyRecord).where(CentralSurveyRecord.organization_unit_uid == uid)): reasons.append("已有正式成果")
        if db.scalar(select(func.count()).select_from(OnlineSurveyEntry).where(OnlineSurveyEntry.organization_unit_uid == uid)): reasons.append("已有在线调查记录")
    elif kind == "canals":
        if db.scalar(select(func.count()).select_from(MasterCanal).where(MasterCanal.parent_canal_uid == uid)): reasons.append("仍有下级渠道")
        if db.scalar(select(func.count()).select_from(MasterManagementScope).where(MasterManagementScope.canal_uid == uid)): reasons.append("仍有关联分管范围")
        if db.scalar(select(func.count()).select_from(CentralSurveyRecord).where(CentralSurveyRecord.canal_unit_uid == uid)): reasons.append("已有正式成果")
        if db.scalar(select(func.count()).select_from(OnlineSurveyEntry).where(OnlineSurveyEntry.canal_unit_uid == uid)): reasons.append("已有在线调查记录")
    else:
        if db.scalar(select(func.count()).select_from(OnlineSurveyEntry).where(OnlineSurveyEntry.management_scope_uid == uid)): reasons.append("已有在线调查记录")
        values_list = list(db.scalars(select(SurveyTask.selected_scope_uids)))
        if any(uid in (values or []) for values in values_list): reasons.append("已被调查任务使用")
    if reasons: raise MasterDataInUseError("不能删除：" + "、".join(reasons) + "；可保持停用以保留历史。")
    db.delete(row); _bump(db, username); db.commit()
