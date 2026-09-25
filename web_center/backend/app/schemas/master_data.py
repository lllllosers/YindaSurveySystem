from pydantic import BaseModel


class MasterDataSummary(BaseModel):
    contract_schema_version: str
    master_data_version: str
    management_scope_version: str
    source_description: str
    contract_sha256: str
    department_count: int
    office_count: int
    canal_count: int
    management_scope_count: int


class DepartmentRead(BaseModel):
    master_key: str
    stable_uid: str
    name: str
    business_code: str
    sort_order: int
    description: str | None = None


class OfficeRead(DepartmentRead):
    parent_master_key: str
    parent_name: str


class CanalRead(BaseModel):
    master_key: str
    stable_uid: str
    name: str
    canal_level: str
    parent_master_key: str | None = None
    parent_name: str | None = None
    sort_order: int
    description: str | None = None


class ManagementScopeRead(BaseModel):
    master_key: str
    stable_uid: str
    canal_master_key: str
    canal_name: str
    organization_master_key: str
    organization_name: str
    range_mode: str
    start_stake_text: str | None = None
    start_stake_value: float | None = None
    end_stake_text: str | None = None
    end_stake_value: float | None = None
    sort_order: int
    status: str
    description: str | None = None


class MasterDataSnapshot(BaseModel):
    summary: MasterDataSummary
    departments: list[DepartmentRead]
    offices: list[OfficeRead]
    canals: list[CanalRead]
    management_scopes: list[ManagementScopeRead]
