from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

from app.schemas.master_data import (
    CanalRead,
    DepartmentRead,
    ManagementScopeRead,
    MasterDataSnapshot,
    MasterDataSummary,
    OfficeRead,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = (
    REPOSITORY_ROOT
    / "shared"
    / "master_data"
    / "official_master_contract.json"
)
SUPPORTED_CONTRACT_SCHEMA_VERSION = "1.0"
ALLOWED_RANGE_MODES = {
    "whole",
    "segment_known",
    "segment_unknown",
}


def deterministic_master_uid(
    identity_namespace: str,
    entity_kind: str,
    master_key: str,
) -> str:
    payload = (
        f"{identity_namespace}:"
        f"{entity_kind}:"
        f"{master_key}"
    ).encode("utf-8")
    return sha256(payload).hexdigest()[:32]


def _require_text(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(
            f"正式主数据契约字段 {key!r} 必须是非空字符串。"
        )
    return value


def _require_records(data: dict, key: str) -> list[dict]:
    value = data.get(key)
    if not isinstance(value, list):
        raise RuntimeError(
            f"正式主数据契约字段 {key!r} 必须是数组。"
        )
    if not all(isinstance(item, dict) for item in value):
        raise RuntimeError(
            f"正式主数据契约字段 {key!r} 只能包含对象。"
        )
    return value


def _master_key_map(
    records: list[dict],
    label: str,
) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for record in records:
        master_key = record.get("master_key")
        if not isinstance(master_key, str) or not master_key.strip():
            raise RuntimeError(f"{label}记录缺少有效 master_key。")
        if master_key in result:
            raise RuntimeError(f"{label}存在重复 master_key：{master_key}。")
        result[master_key] = record
    return result


def _validate_contract(data: dict) -> None:
    schema_version = _require_text(data, "contract_schema_version")
    if schema_version != SUPPORTED_CONTRACT_SCHEMA_VERSION:
        raise RuntimeError(
            "不支持的正式主数据契约版本："
            f"{schema_version}。"
        )

    for key in (
        "identity_namespace",
        "master_data_version",
        "master_data_source",
        "management_scope_version",
        "management_scope_source",
    ):
        _require_text(data, key)

    departments = _require_records(data, "departments")
    offices = _require_records(data, "offices")
    canals = _require_records(data, "canals")
    scopes = _require_records(data, "management_scopes")

    department_map = _master_key_map(departments, "管理处")
    office_map = _master_key_map(offices, "管理所")
    canal_map = _master_key_map(canals, "渠道")
    _master_key_map(scopes, "渠道管理范围")

    for office in offices:
        if office.get("parent_master_key") not in department_map:
            raise RuntimeError(
                "管理所引用了不存在的管理处："
                f"{office.get('master_key')}。"
            )

    for canal in canals:
        parent_key = canal.get("parent_master_key")
        if parent_key is not None and parent_key not in canal_map:
            raise RuntimeError(
                "渠道引用了不存在的上级渠道："
                f"{canal.get('master_key')}。"
            )

    for scope in scopes:
        if scope.get("canal_master_key") not in canal_map:
            raise RuntimeError(
                "管理范围引用了不存在的渠道："
                f"{scope.get('master_key')}。"
            )
        if scope.get("organization_master_key") not in office_map:
            raise RuntimeError(
                "管理范围引用了不存在的末级管理单位："
                f"{scope.get('master_key')}。"
            )
        if scope.get("range_mode") not in ALLOWED_RANGE_MODES:
            raise RuntimeError(
                "管理范围使用了无效 range_mode："
                f"{scope.get('master_key')}。"
            )


@lru_cache(maxsize=1)
def load_contract() -> tuple[dict, str]:
    try:
        raw = CONTRACT_PATH.read_bytes()
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"正式主数据契约不存在：{CONTRACT_PATH}。"
        ) from exc

    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("正式主数据契约不是有效 UTF-8 JSON。") from exc

    if not isinstance(data, dict):
        raise RuntimeError("正式主数据契约根节点必须是对象。")

    _validate_contract(data)
    return data, sha256(raw).hexdigest()


@lru_cache(maxsize=1)
def get_snapshot() -> MasterDataSnapshot:
    data, contract_sha256 = load_contract()
    namespace = str(data["identity_namespace"])

    department_map = {
        str(item["master_key"]): item
        for item in data["departments"]
    }
    office_map = {
        str(item["master_key"]): item
        for item in data["offices"]
    }
    canal_map = {
        str(item["master_key"]): item
        for item in data["canals"]
    }

    departments = [
        DepartmentRead(
            **item,
            stable_uid=deterministic_master_uid(
                namespace,
                "organization",
                str(item["master_key"]),
            ),
        )
        for item in data["departments"]
    ]
    offices = [
        OfficeRead(
            **item,
            stable_uid=deterministic_master_uid(
                namespace,
                "organization",
                str(item["master_key"]),
            ),
            parent_name=str(
                department_map[str(item["parent_master_key"])]["name"]
            ),
        )
        for item in data["offices"]
    ]
    canals = [
        CanalRead(
            master_key=str(item["master_key"]),
            stable_uid=deterministic_master_uid(
                namespace,
                "canal",
                str(item["master_key"]),
            ),
            name=str(item["name"]),
            canal_level=str(item["canal_level"]),
            parent_master_key=item.get("parent_master_key"),
            parent_name=(
                str(canal_map[str(item["parent_master_key"])]["name"])
                if item.get("parent_master_key") is not None
                else None
            ),
            sort_order=int(item.get("sort_order", 0)),
            description=item.get("description"),
        )
        for item in data["canals"]
    ]
    scopes = [
        ManagementScopeRead(
            **item,
            stable_uid=deterministic_master_uid(
                namespace,
                "canal_management_scope",
                str(item["master_key"]),
            ),
            canal_name=str(
                canal_map[str(item["canal_master_key"])]["name"]
            ),
            organization_name=str(
                office_map[str(item["organization_master_key"])]["name"]
            ),
        )
        for item in data["management_scopes"]
    ]

    return MasterDataSnapshot(
        summary=MasterDataSummary(
            contract_schema_version=str(data["contract_schema_version"]),
            master_data_version=str(data["master_data_version"]),
            management_scope_version=str(data["management_scope_version"]),
            source_description=str(data["master_data_source"]),
            contract_sha256=contract_sha256,
            department_count=len(departments),
            office_count=len(offices),
            canal_count=len(canals),
            management_scope_count=len(scopes),
        ),
        departments=departments,
        offices=offices,
        canals=canals,
        management_scopes=scopes,
    )
