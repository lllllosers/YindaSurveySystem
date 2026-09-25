from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field


class PackageIssueRead(BaseModel):
    code: str
    message: str
    path: str | None = None


class WorkflowIssueRead(BaseModel):
    severity: str
    code: str
    message: str
    entity_uid: str = ""


class ResultReviewRequest(BaseModel):
    decision: Literal["accepted", "rejected"]
    notes: str | None = Field(default=None, max_length=4000)


class ResultImportRead(BaseModel):
    submission_uid: str
    status: str
    assets: int
    records: int
    inspections: int
    media: int
    changed_records: int


class ResultSubmissionRead(BaseModel):
    submission_uid: str
    package_uid: str | None
    result_uid: str | None
    project_uid: str | None
    survey_batch_uid: str | None
    original_filename: str
    file_sha256: str
    file_size: int
    package_format_version: str | None
    desktop_app_version: str | None
    desktop_app_version_label: str | None
    result_name: str | None
    source_task_uids: list[str]
    submission_task_uid: str | None
    counts: dict
    status: str
    inspection_error_count: int
    inspection_issues: list[PackageIssueRead]
    preflight_error_count: int
    preflight_warning_count: int
    preflight_issues: list[WorkflowIssueRead]
    preflight_summary: dict[str, int]
    preflight_checked_at: datetime | None
    review_notes: str | None
    reviewed_by_username: str | None
    reviewed_at: datetime | None
    imported_at: datetime | None
    storage_status: str
    storage_checked_at: datetime | None
    uploader_user_uid: str
    uploader_username: str
    uploaded_at: datetime


class ResultSubmissionPage(BaseModel):
    items: list[ResultSubmissionRead]
    total: int
    limit: int
    offset: int
