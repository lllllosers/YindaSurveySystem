from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


TaskTargetType = Literal["department", "water_office"]
TaskStatus = Literal["issued", "downloaded", "result_received", "closed", "cancelled"]


class SurveyTaskCreate(BaseModel):
    project_uid: str = Field(min_length=32, max_length=32)
    survey_batch_uid: str = Field(min_length=32, max_length=32)
    task_name: str = Field(min_length=1, max_length=240)
    notes: str | None = Field(default=None, max_length=2000)
    target_unit_type: TaskTargetType
    target_master_key: str = Field(min_length=1, max_length=100)
    selected_management_scope_uids: list[str] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def normalize(self) -> "SurveyTaskCreate":
        self.task_name = self.task_name.strip()
        self.target_master_key = self.target_master_key.strip()
        self.notes = self.notes.strip() if self.notes else None
        self.selected_management_scope_uids = list(
            dict.fromkeys(value.strip() for value in self.selected_management_scope_uids)
        )
        if not self.task_name or not self.target_master_key:
            raise ValueError("任务名称和目标单位不能为空")
        if not self.selected_management_scope_uids or any(
            not value for value in self.selected_management_scope_uids
        ):
            raise ValueError("调查任务至少需要一个有效分管范围")
        return self


class SurveyTaskRead(BaseModel):
    task_uid: str
    package_uid: str
    project_uid: str
    project_name: str
    survey_batch_uid: str
    batch_name: str
    batch_code: str
    task_name: str
    notes: str | None
    target_unit_type: TaskTargetType
    department_uid: str
    department_name: str
    organization_unit_uid: str
    organization_name: str
    parent_task_uid: str | None
    root_task_uid: str
    task_depth: int
    selected_scope_count: int
    reference_canal_count: int
    reference_organization_count: int
    form_count: int
    file_sha256: str
    file_size: int
    status: TaskStatus
    download_count: int
    first_downloaded_at: datetime | None
    last_downloaded_at: datetime | None
    created_by_username: str
    created_at: datetime
    source_channel: Literal["web_center", "desktop_handover"]
    source_filename: str | None


class FrozenScopeRead(BaseModel):
    management_scope_uid: str
    canal_uid: str
    canal_name: str
    organization_unit_uid: str
    organization_name: str
    range_mode: str
    start_stake_text: str | None
    end_stake_text: str | None
    description: str | None


class SurveyTaskDetail(SurveyTaskRead):
    selected_management_scope_uids: list[str]
    frozen_scopes: list[FrozenScopeRead]
    master_data_version: str
    master_contract_sha256: str
    form_contract_version: str


class SurveyTaskPage(BaseModel):
    items: list[SurveyTaskRead]
    total: int
    limit: int
    offset: int
