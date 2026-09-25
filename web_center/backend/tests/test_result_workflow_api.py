from __future__ import annotations

from hashlib import sha256
import io
import json
from pathlib import Path
import shutil
import zipfile
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.main import app
from app.models.central_record import (
    CentralEngineeringAsset,
    CentralInspectionResult,
    CentralSurveyMedia,
    CentralSurveyRecord,
)
from app.models.result_submission import ResultSubmission
from app.models.survey_task import SurveyTask
from app.services.master_data_service import get_snapshot
from app.services.result_submission_service import BACKEND_ROOT as RESULT_BACKEND_ROOT
from app.services.survey_task_service import BACKEND_ROOT as TASK_BACKEND_ROOT
from tests.auth_helpers import cleanup_test_user, create_test_user, login_client


def encode_json(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def create_project_batch_and_task(
    client: TestClient,
    csrf: str,
    token: str,
) -> tuple[str, str, dict, object]:
    project = client.post(
        "/api/v1/projects",
        headers={"X-CSRF-Token": csrf},
        json={"name": f"成果闭环测试-{token}", "short_name": "闭环测试", "status": "active"},
    )
    assert project.status_code == 201, project.text
    project_uid = project.json()["project_uid"]
    batch = client.post(
        f"/api/v1/projects/{project_uid}/batches",
        headers={"X-CSRF-Token": csrf},
        json={
            "batch_name": f"成果闭环批次-{token}",
            "batch_code": f"FLOW-{token}",
            "start_date": "2026-09-01",
            "end_date": "2026-12-31",
            "status": "active",
        },
    )
    assert batch.status_code == 201, batch.text
    batch_uid = batch.json()["survey_batch_uid"]
    scope = get_snapshot().management_scopes[0]
    office = next(
        item for item in get_snapshot().offices
        if item.master_key == scope.organization_master_key
    )
    task = client.post(
        "/api/v1/survey-tasks",
        headers={"X-CSRF-Token": csrf},
        json={
            "project_uid": project_uid,
            "survey_batch_uid": batch_uid,
            "task_name": "成果闭环正式协议测试",
            "target_unit_type": "water_office",
            "target_master_key": office.master_key,
            "selected_management_scope_uids": [scope.stable_uid],
        },
    )
    assert task.status_code == 201, task.text
    task_data = task.json()
    return project_uid, batch_uid, task_data, task_data["frozen_scopes"][0]


def make_formal_result_package(
    *,
    project_uid: str,
    batch_uid: str,
    task_uid: str,
    scope,
) -> tuple[bytes, str, str]:
    package_uid = uuid4().hex
    result_uid = uuid4().hex
    asset_uid = uuid4().hex
    record_uid = uuid4().hex
    created_at = "2026-09-25T12:00:00+08:00"
    asset = {
        "engineering_asset_uid": asset_uid,
        "project_uid": project_uid,
        "asset_name": "自动化测试防渗渠段",
        "asset_type": "lined_channel_section",
        "organization_unit_uid": scope["organization_unit_uid"],
        "canal_unit_uid": scope["canal_uid"],
        "business_code": "TEST-001",
        "code_scheme_version": "V1",
        "single_stake_text": None,
        "single_stake_value": None,
        "start_stake_text": "0+000",
        "start_stake_value": 0,
        "end_stake_text": "0+100",
        "end_stake_value": 100,
        "first_survey_batch_uid": batch_uid,
        "status": "active",
        "notes": "自动化测试数据",
        "created_at": created_at,
        "updated_at": created_at,
        "revision_no": 1,
    }
    record = {
        "survey_record_uid": record_uid,
        "source_task_uid": task_uid,
        "source_management_scope_uid": scope["management_scope_uid"],
        "project_uid": project_uid,
        "survey_batch_uid": batch_uid,
        "form": {
            "form_code": "form_2_1",
            "form_number": "2.1",
            "form_name": "防渗衬砌渠道渠段工程状况调查表",
            "asset_type": "lined_channel_section",
            "version_code": "V2",
            "version_name": "2026起止桩号统一版",
            "effective_date": "2026-09-23",
        },
        "record_type": "engineering",
        "organization_unit_uid": scope["organization_unit_uid"],
        "canal_unit_uid": scope["canal_uid"],
        "engineering_asset_uid": asset_uid,
        "business_code": "TEST-001",
        "survey_date": "2026-09-25",
        "overall_grade": "良好",
        "survey_comment": "自动化测试",
        "surveyor_signatures": "测试员",
        "water_office_manager_signature": None,
        "engineering_section_chief_signature": None,
        "department_head_signature": None,
        "record_status": "completed",
        "record_data": {"lining_condition": "正常"},
        "void_reason": None,
        "created_at": created_at,
        "updated_at": created_at,
        "revision_no": 1,
    }
    inspection = {
        "survey_record_uid": record_uid,
        "item_code": "lining",
        "category": "渠道工程",
        "item_name": "衬砌状态",
        "grade": "良好",
        "description": "结构完整",
        "remark": None,
        "updated_at": created_at,
    }
    result = {
        "result_schema_version": "2.2",
        "result_uid": result_uid,
        "result_name": "成果闭环测试包",
        "source_task_uid": task_uid,
        "source_task_uids": [task_uid],
        "submission_task_uid": task_uid,
        "project": {"project_uid": project_uid, "name": "测试项目", "short_name": "测试"},
        "survey_batch": {
            "survey_batch_uid": batch_uid,
            "batch_name": "测试批次",
            "batch_code": "FLOW",
            "start_date": "2026-09-01",
            "end_date": "2026-12-31",
        },
        "creator": "pytest",
        "notes": None,
        "counts": {
            "engineering_assets": 1,
            "survey_records": 1,
            "inspection_results": 1,
            "survey_media": 0,
        },
        "created_at": created_at,
    }
    payloads = {
        "result.json": encode_json(result),
        "data/engineering_assets.json": encode_json({"items": [asset]}),
        "data/survey_records.json": encode_json({"items": [record]}),
        "data/inspection_results.json": encode_json({"items": [inspection]}),
        "data/survey_media.json": encode_json({"items": []}),
    }
    manifest = {
        "package_uid": package_uid,
        "package_format_version": "1.0",
        "package_kind": "survey_result",
        "result_schema_version": "2.2",
        "created_at": created_at,
        "app_version": "1.2.0",
        "app_version_label": "V1.2.0",
        "result_uid": result_uid,
        "source_task_uid": task_uid,
        "source_task_uids": [task_uid],
        "submission_task_uid": task_uid,
        "project_uid": project_uid,
        "survey_batch_uid": batch_uid,
        "files": [
            {"path": path, "sha256": sha256(content).hexdigest(), "size": len(content)}
            for path, content in sorted(payloads.items())
        ],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", encode_json(manifest))
        for path, content in payloads.items():
            archive.writestr(path, content)
    return buffer.getvalue(), asset_uid, record_uid


def cleanup_workflow(submission_uid: str | None, task_uid: str | None, record_uid: str | None, asset_uid: str | None) -> None:
    with SessionLocal() as db:
        if record_uid:
            db.execute(delete(CentralInspectionResult).where(CentralInspectionResult.survey_record_uid == record_uid))
            db.execute(delete(CentralSurveyMedia).where(CentralSurveyMedia.survey_record_uid == record_uid))
            db.execute(delete(CentralSurveyRecord).where(CentralSurveyRecord.survey_record_uid == record_uid))
        if asset_uid:
            db.execute(delete(CentralEngineeringAsset).where(CentralEngineeringAsset.engineering_asset_uid == asset_uid))
        if submission_uid:
            row = db.scalar(select(ResultSubmission).where(ResultSubmission.submission_uid == submission_uid))
            if row is not None:
                folder = (RESULT_BACKEND_ROOT / row.stored_relative_path).parent
                db.delete(row)
                db.commit()
                shutil.rmtree(folder, ignore_errors=True)
        if task_uid:
            task = db.scalar(select(SurveyTask).where(SurveyTask.task_uid == task_uid))
            if task is not None:
                folder = (TASK_BACKEND_ROOT / task.stored_relative_path).parent
                db.delete(task)
                db.commit()
                shutil.rmtree(folder, ignore_errors=True)
        db.commit()


def test_formal_result_preflight_review_import_and_query() -> None:
    token = uuid4().hex[:8]
    admin = create_test_user("admin")
    client = TestClient(app)
    csrf = login_client(client, admin.username)
    project_uid = batch_uid = task_uid = submission_uid = None
    asset_uid = record_uid = None
    try:
        project_uid, batch_uid, task, scope = create_project_batch_and_task(client, csrf, token)
        task_uid = task["task_uid"]
        package, asset_uid, record_uid = make_formal_result_package(
            project_uid=project_uid,
            batch_uid=batch_uid,
            task_uid=task_uid,
            scope=scope,
        )
        uploaded = client.post(
            "/api/v1/result-submissions/upload",
            headers={"X-CSRF-Token": csrf},
            files={"file": ("formal.ydresult", package, "application/octet-stream")},
        )
        assert uploaded.status_code == 201, uploaded.text
        submission_uid = uploaded.json()["submission_uid"]
        assert uploaded.json()["submission_task_uid"] == task_uid

        preflight = client.post(
            f"/api/v1/result-submissions/{submission_uid}/preflight",
            headers={"X-CSRF-Token": csrf},
        )
        assert preflight.status_code == 200, preflight.text
        assert preflight.json()["status"] == "preflight_passed"
        assert preflight.json()["preflight_summary"]["new_records"] == 1

        reviewed = client.post(
            f"/api/v1/result-submissions/{submission_uid}/review",
            headers={"X-CSRF-Token": csrf},
            json={"decision": "accepted", "notes": "自动化审核通过"},
        )
        assert reviewed.status_code == 200, reviewed.text
        assert reviewed.json()["status"] == "accepted"

        imported = client.post(
            f"/api/v1/result-submissions/{submission_uid}/import",
            headers={"X-CSRF-Token": csrf},
        )
        assert imported.status_code == 200, imported.text
        assert imported.json()["status"] == "imported"
        assert imported.json()["records"] == 1

        detail = client.get(f"/api/v1/central-records/{record_uid}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["asset_name"] == "自动化测试防渗渠段"
        assert len(detail.json()["inspections"]) == 1
        assert detail.json()["source_task_uid"] == task_uid

        task_detail = client.get(f"/api/v1/survey-tasks/{task_uid}")
        assert task_detail.status_code == 200
        assert task_detail.json()["status"] == "closed"
    finally:
        cleanup_workflow(submission_uid, task_uid, record_uid, asset_uid)
        if batch_uid:
            client.delete(f"/api/v1/survey-batches/{batch_uid}", headers={"X-CSRF-Token": csrf})
        if project_uid:
            client.delete(f"/api/v1/projects/{project_uid}", headers={"X-CSRF-Token": csrf})
        cleanup_test_user(admin.user_uid)
