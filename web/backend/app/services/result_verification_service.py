from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy.orm import Session

from app.models.result_submission import ResultSubmission
from app.services.result_package_inspection import inspect_result_package
from app.services.result_submission_service import (
    BACKEND_ROOT,
    STORAGE_ROOT,
)


CHUNK_SIZE = 1024 * 1024


def calculate_sha256(path) -> tuple[str, int]:
    digest = sha256()
    size = 0

    with path.open("rb") as source:
        while True:
            chunk = source.read(CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)

    return digest.hexdigest(), size


def resolve_stored_path(row: ResultSubmission):
    path = (BACKEND_ROOT / row.stored_relative_path).resolve()
    root = STORAGE_ROOT.resolve()

    if path == root or root not in path.parents:
        raise RuntimeError("成果包存储路径越界。")

    return path


def verify_submission_file(
    db: Session,
    row: ResultSubmission,
) -> dict:
    checked_at = datetime.now(timezone.utc)
    path = resolve_stored_path(row)

    file_exists = path.is_file()
    actual_size = None
    actual_sha256 = None
    size_match = False
    sha256_match = False
    package_structure_valid = None
    package_structure_error_count = None
    package_structure_issues: list[dict] = []

    if not file_exists:
        storage_status = "missing"
    else:
        actual_sha256, actual_size = calculate_sha256(path)
        size_match = actual_size == row.file_size
        sha256_match = actual_sha256 == row.file_sha256

        if not size_match:
            storage_status = "size_mismatch"
        elif not sha256_match:
            storage_status = "hash_mismatch"
        else:
            inspection = inspect_result_package(path)
            package_structure_valid = inspection.valid
            package_structure_error_count = inspection.error_count
            package_structure_issues = [
                issue.as_dict()
                for issue in inspection.issues
            ]
            storage_status = (
                "ok"
                if inspection.valid
                else "package_invalid"
            )

    details = {
        "file_exists": file_exists,
        "expected_size": row.file_size,
        "actual_size": actual_size,
        "size_match": size_match,
        "expected_sha256": row.file_sha256,
        "actual_sha256": actual_sha256,
        "sha256_match": sha256_match,
        "package_structure_valid": package_structure_valid,
        "package_structure_error_count": package_structure_error_count,
        "package_structure_issues": package_structure_issues,
    }

    row.storage_status = storage_status
    row.storage_checked_at = checked_at
    row.storage_check_json = details
    db.commit()
    db.refresh(row)

    return {
        "submission_uid": row.submission_uid,
        "storage_status": storage_status,
        "checked_at": checked_at,
        **details,
    }
