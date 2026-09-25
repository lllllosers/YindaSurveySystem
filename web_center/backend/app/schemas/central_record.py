from datetime import datetime

from pydantic import BaseModel


class CentralRecordRead(BaseModel):
    survey_record_uid: str
    engineering_asset_uid: str
    asset_name: str | None
    asset_type: str | None
    business_code: str | None
    project_uid: str
    survey_batch_uid: str
    form_code: str
    organization_unit_uid: str
    organization_name: str
    canal_unit_uid: str
    canal_name: str
    source_task_uid: str | None
    source_management_scope_uid: str | None
    record_status: str | None
    revision_no: int
    current_submission_uid: str
    imported_at: datetime
    updated_at: datetime


class CentralRecordDetail(CentralRecordRead):
    record_payload: dict
    asset_payload: dict
    inspections: list[dict]
    media: list[dict]


class CentralRecordPage(BaseModel):
    items: list[CentralRecordRead]
    total: int
    limit: int
    offset: int


class NamedCount(BaseModel):
    key: str
    name: str
    count: int


class CentralRecordSummary(BaseModel):
    asset_count: int
    record_count: int
    inspection_count: int
    media_count: int
    by_form: list[NamedCount]
    by_organization: list[NamedCount]
    by_canal: list[NamedCount]
