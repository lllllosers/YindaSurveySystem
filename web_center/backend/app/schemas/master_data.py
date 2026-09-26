from typing import Literal

from pydantic import BaseModel, Field, model_validator


MasterStatus = Literal["active", "inactive"]
RangeMode = Literal["whole", "segment_known", "segment_unknown"]


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
    status: MasterStatus = "active"


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
    status: MasterStatus = "active"


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


class DepartmentWrite(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    business_code: str = Field(min_length=1, max_length=40)
    sort_order: int = 0
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def normalize(self):
        self.name = self.name.strip()
        self.business_code = self.business_code.strip()
        self.description = self.description.strip() if self.description else None
        return self


class OfficeWrite(DepartmentWrite):
    parent_department_uid: str = Field(min_length=32, max_length=32)


class CanalWrite(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    canal_level: Literal["01", "02", "03", "04"]
    parent_canal_uid: str | None = Field(default=None, min_length=32, max_length=32)
    sort_order: int = 0
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def normalize(self):
        self.name = self.name.strip()
        self.description = self.description.strip() if self.description else None
        return self


class ManagementScopeWrite(BaseModel):
    canal_uid: str = Field(min_length=32, max_length=32)
    organization_unit_uid: str = Field(min_length=32, max_length=32)
    range_mode: RangeMode
    start_stake_text: str | None = Field(default=None, max_length=40)
    end_stake_text: str | None = Field(default=None, max_length=40)
    sort_order: int = 0
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def normalize(self):
        self.start_stake_text = self.start_stake_text.strip() if self.start_stake_text else None
        self.end_stake_text = self.end_stake_text.strip() if self.end_stake_text else None
        self.description = self.description.strip() if self.description else None
        if self.range_mode == "segment_known" and (not self.start_stake_text or not self.end_stake_text):
            raise ValueError("已知分段必须填写起止桩号")
        if self.range_mode != "segment_known":
            self.start_stake_text = None
            self.end_stake_text = None
        return self


class MasterStatusUpdate(BaseModel):
    status: MasterStatus
