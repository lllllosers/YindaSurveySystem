from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


OnlineEntryStatus = Literal["draft", "submitted", "accepted", "rejected", "imported"]


class OnlineEntryPayload(BaseModel):
    task_uid: str = Field(min_length=32, max_length=32)
    management_scope_uid: str = Field(min_length=32, max_length=32)
    form_code: str = Field(min_length=1, max_length=80)
    form_data: dict = Field(default_factory=dict)
    evaluations: list[dict] = Field(default_factory=list)
    conclusion: dict = Field(default_factory=dict)


class OnlineEntryUpdate(BaseModel):
    form_data: dict = Field(default_factory=dict)
    evaluations: list[dict] = Field(default_factory=list)
    conclusion: dict = Field(default_factory=dict)


class OnlineEntryReview(BaseModel):
    decision: Literal["accept", "reject"]
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def normalize(self) -> "OnlineEntryReview":
        self.notes = self.notes.strip() if self.notes else None
        if self.decision == "reject" and not self.notes:
            raise ValueError("退回时请填写修改意见")
        return self


class OnlineEntryRead(BaseModel):
    entry_uid: str
    task_uid: str
    task_name: str
    project_uid: str
    project_name: str
    survey_batch_uid: str
    batch_name: str
    management_scope_uid: str
    organization_unit_uid: str
    organization_name: str
    canal_unit_uid: str
    canal_name: str
    form_code: str
    form_name: str
    asset_name: str | None
    form_data: dict
    evaluations: list[dict]
    conclusion: dict
    status: OnlineEntryStatus
    revision_no: int
    review_notes: str | None
    created_by_username: str
    submitted_at: datetime | None
    reviewed_by_username: str | None
    reviewed_at: datetime | None
    imported_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OnlineEntryPage(BaseModel):
    items: list[OnlineEntryRead]
    total: int
    limit: int
    offset: int


class FormFieldRead(BaseModel):
    key: str
    label: str
    display_label: str
    input_type: str
    required: bool
    unit: str | None
    placeholder: str | None
    maximum: int | None
    choices: list[str]


class FormRowRead(BaseModel):
    field_keys: list[str]
    label: str | None
    separator: str | None


class FormSectionRead(BaseModel):
    title: str
    rows: list[FormRowRead]


class OnlineFormDefinitionRead(BaseModel):
    form_code: str
    form_number: str
    form_name: str
    asset_type: str
    asset_name_field: str
    fields: list[FormFieldRead]
    sections: list[FormSectionRead]
    evaluation_items: list[dict]
    grade_options: list[str]
    evaluation_title: str
    evaluation_note: str | None
    conclusion_title: str
