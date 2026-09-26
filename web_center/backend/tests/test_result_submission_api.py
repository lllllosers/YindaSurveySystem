from __future__ import annotations

from hashlib import sha256
import io
import json
import shutil
import zipfile

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.result_submission import ResultSubmission
from app.services.result_submission_service import BACKEND_ROOT
from tests.auth_helpers import cleanup_test_user, create_test_user, login_client


def encode_json(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def make_package() -> bytes:
    package_uid = "1" * 32
    result_uid = "2" * 32
    project_uid = "3" * 32
    batch_uid = "4" * 32

    result = {
        "result_uid": result_uid,
        "result_name": "API 测试成果",
        "source_task_uid": None,
        "source_task_uids": [],
        "project": {"project_uid": project_uid, "name": "测试项目", "short_name": "测试"},
        "survey_batch": {
            "survey_batch_uid": batch_uid,
            "batch_name": "测试批次",
            "batch_code": "TEST",
            "start_date": None,
            "end_date": None,
        },
        "creator": "pytest",
        "notes": None,
        "counts": {
            "engineering_assets": 0,
            "survey_records": 0,
            "inspection_results": 0,
            "survey_media": 0,
        },
        "created_at": "2026-09-18T00:00:00+08:00",
    }

    payloads = {
        "result.json": encode_json(result),
        "data/engineering_assets.json": encode_json({"items": []}),
        "data/survey_records.json": encode_json({"items": []}),
        "data/inspection_results.json": encode_json({"items": []}),
        "data/survey_media.json": encode_json({"items": []}),
    }

    manifest = {
        "package_uid": package_uid,
        "package_format_version": "1.0",
        "package_kind": "survey_result",
        "created_at": "2026-09-18T00:00:00+08:00",
        "app_version": "0.7.0",
        "app_version_label": "V0.7.0",
        "result_uid": result_uid,
        "source_task_uid": None,
        "source_task_uids": [],
        "project_uid": project_uid,
        "survey_batch_uid": batch_uid,
        "files": [
            {
                "path": path,
                "sha256": sha256(content).hexdigest(),
                "size": len(content),
            }
            for path, content in sorted(payloads.items())
        ],
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", encode_json(manifest))
        for path, content in payloads.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def cleanup_submission(submission_uid: str) -> None:
    with SessionLocal() as db:
        row = db.query(ResultSubmission).filter(
            ResultSubmission.submission_uid == submission_uid
        ).one_or_none()
        if row is None:
            return
        folder = (BACKEND_ROOT / row.stored_relative_path).parent
        db.delete(row)
        db.commit()
        shutil.rmtree(folder, ignore_errors=True)


def test_result_package_upload_and_permissions() -> None:
    admin = create_test_user("admin")
    viewer = create_test_user("viewer")
    submission_uid = None
    package = make_package()

    try:
        admin_client = TestClient(app)
        admin_csrf = login_client(admin_client, admin.username)

        response = admin_client.post(
            "/api/v1/result-submissions/upload",
            headers={"X-CSRF-Token": admin_csrf},
            files={"file": ("test.ydresult", package, "application/octet-stream")},
        )
        assert response.status_code == 201, response.text
        data = response.json()
        submission_uid = data["submission_uid"]
        assert data["status"] == "inspected"
        assert data["inspection_error_count"] == 0

        filtered = admin_client.get(
            "/api/v1/result-submissions",
            params={
                "project_uid": "3" * 32,
                "survey_batch_uid": "4" * 32,
                "keyword": "API 测试成果",
                "limit": 1,
            },
        )
        assert filtered.status_code == 200, filtered.text
        assert filtered.json()["total"] == 1
        assert filtered.json()["items"][0]["submission_uid"] == submission_uid
        assert filtered.json()["summary"]["total"] == 1
        assert filtered.json()["summary"]["awaiting_check"] == 1

        response = admin_client.get("/api/v1/result-submissions")
        assert response.status_code == 200
        assert any(
            item["submission_uid"] == submission_uid
            for item in response.json()["items"]
        )

        viewer_client = TestClient(app)
        viewer_csrf = login_client(viewer_client, viewer.username)

        assert viewer_client.get("/api/v1/result-submissions").status_code == 200

        response = viewer_client.post(
            "/api/v1/result-submissions/upload",
            headers={"X-CSRF-Token": viewer_csrf},
            files={"file": ("viewer.ydresult", package, "application/octet-stream")},
        )
        assert response.status_code == 403

    finally:
        if submission_uid is not None:
            cleanup_submission(submission_uid)
        cleanup_test_user(viewer.user_uid)
        cleanup_test_user(admin.user_uid)
