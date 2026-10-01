from datetime import datetime

from pydantic import BaseModel


class ResultFileVerificationRead(BaseModel):
    submission_uid: str
    storage_status: str
    checked_at: datetime
    file_exists: bool
    expected_size: int
    actual_size: int | None
    size_match: bool
    expected_sha256: str
    actual_sha256: str | None
    sha256_match: bool
    package_structure_valid: bool | None
    package_structure_error_count: int | None
    package_structure_issues: list[dict]
