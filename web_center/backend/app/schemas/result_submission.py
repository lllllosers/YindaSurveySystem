from datetime import datetime
from pydantic import BaseModel


class PackageIssueRead(BaseModel):
    code: str
    message: str
    path: str | None = None


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
    counts: dict
    status: str
    inspection_error_count: int
    inspection_issues: list[PackageIssueRead]
    uploader_user_uid: str
    uploader_username: str
    uploaded_at: datetime


class ResultSubmissionPage(BaseModel):
    items: list[ResultSubmissionRead]
    total: int
    limit: int
    offset: int
