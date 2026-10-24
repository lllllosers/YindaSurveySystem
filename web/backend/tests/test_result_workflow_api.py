from __future__ import annotations

from hashlib import sha256
import base64
from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import shutil
from threading import Event
import zipfile
from uuid import uuid4

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select

from app.db.session import SessionLocal
from app.db.session import engine
from app.main import app
from app.models.central_record import (
    CentralEngineeringAsset,
    CentralInspectionResult,
    CentralSurveyMedia,
    CentralSurveyRecord,
)
from app.models.result_submission import ResultSubmission
from app.models.online_entry import OnlineSurveyEntry
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
    *,
    department: bool = False,
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
            "target_unit_type": "department" if department else "water_office",
            "target_master_key": office.parent_master_key if department else office.master_key,
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
    record_count: int = 1,
    media_count: int = 0,
    media_uid_length: int = 36,
    source_task_uids: tuple[str, ...] | None = None,
) -> tuple[bytes, str, str]:
    source_task_uids = source_task_uids or (task_uid,)
    single_source_task_uid = source_task_uids[0] if len(source_task_uids) == 1 else None
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
    assets, records, inspections, media = [], [], [], []
    media_files = {}
    for index in range(record_count):
        next_asset_uid = asset_uid if index == 0 else uuid4().hex
        next_record_uid = record_uid if index == 0 else uuid4().hex
        assets.append({**asset, "engineering_asset_uid": next_asset_uid,
                       "asset_name": asset["asset_name"] + (f"-{index}" if index else "")})
        records.append({**record, "engineering_asset_uid": next_asset_uid, "survey_record_uid": next_record_uid,
                        "source_task_uid": source_task_uids[index % len(source_task_uids)]})
        inspections.append({**inspection, "survey_record_uid": next_record_uid})
    for index in range(media_count):
        uid = str(uuid4()) if media_uid_length == 36 else uuid4().hex
        path = f"media/{uid}.png"
        # A one pixel PNG, embedded so the fixture needs no image dependency.
        content = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jBZwAAAAASUVORK5CYII="
        )
        media_files[path] = content
        media.append({
            "media_uid": uid, "survey_record_uid": records[index % record_count]["survey_record_uid"],
            "media_kind": "photo", "media_role": "overview", "item_code": None,
            "part_name": None, "sequence_no": index + 1, "original_filename": f"photo-{index}.png",
            "package_path": path, "file_sha256": sha256(content).hexdigest(), "file_size": len(content),
        })
    result = {
        "result_schema_version": "2.2",
        "result_uid": result_uid,
        "result_name": "成果闭环测试包",
        "source_task_uid": single_source_task_uid,
        "source_task_uids": list(source_task_uids),
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
            "engineering_assets": len(assets),
            "survey_records": len(records),
            "inspection_results": len(inspections),
            "survey_media": len(media),
        },
        "created_at": created_at,
    }
    payloads = {
        "result.json": encode_json(result),
        "data/engineering_assets.json": encode_json({"items": assets}),
        "data/survey_records.json": encode_json({"items": records}),
        "data/inspection_results.json": encode_json({"items": inspections}),
        "data/survey_media.json": encode_json({"items": media}),
        **media_files,
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
        "source_task_uid": single_source_task_uid,
        "source_task_uids": list(source_task_uids),
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
        if submission_uid:
            for model in (CentralInspectionResult, CentralSurveyMedia, CentralSurveyRecord, CentralEngineeringAsset):
                db.execute(delete(model).where(model.current_submission_uid == submission_uid))
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
    manager = create_test_user("manager")
    client = TestClient(app)
    csrf = login_client(client, admin.username)
    manager_client = TestClient(app)
    manager_csrf = login_client(manager_client, manager.username)
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
        uploaded = manager_client.post(
            "/api/v1/result-submissions/upload",
            headers={"X-CSRF-Token": manager_csrf},
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

        self_review = manager_client.post(
            f"/api/v1/result-submissions/{submission_uid}/review",
            headers={"X-CSRF-Token": manager_csrf},
            json={"decision": "accepted", "notes": "不能审核自己上传的成果包"},
        )
        assert self_review.status_code == 403

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
        cleanup_test_user(manager.user_uid)
        cleanup_test_user(admin.user_uid)


def test_desktop_preflight_blocks_name_already_waiting_for_web_review() -> None:
    token = uuid4().hex[:8]
    admin = create_test_user("admin")
    client = TestClient(app)
    csrf = login_client(client, admin.username)
    project_uid = batch_uid = task_uid = submission_uid = None
    asset_uid = record_uid = None
    web_entry_uid = uuid4().hex
    try:
        project_uid, batch_uid, task, scope = create_project_batch_and_task(client, csrf, token)
        task_uid = task["task_uid"]
        package, asset_uid, record_uid = make_formal_result_package(
            project_uid=project_uid,
            batch_uid=batch_uid,
            task_uid=task_uid,
            scope=scope,
        )
        with SessionLocal() as db:
            db.add(OnlineSurveyEntry(
                entry_uid=web_entry_uid,
                task_uid=task_uid,
                project_uid=project_uid,
                survey_batch_uid=batch_uid,
                management_scope_uid=scope["management_scope_uid"],
                organization_unit_uid=scope["organization_unit_uid"],
                organization_name=scope["organization_name"],
                canal_unit_uid=scope["canal_uid"],
                canal_name=scope["canal_name"],
                form_code="form_2_1",
                form_name="防渗衬砌渠道渠段工程状况调查表",
                asset_name="自动化测试防渗渠段",
                form_data_json={},
                evaluations_json=[],
                conclusion_json={},
                status="submitted",
                created_by_user_uid=admin.user_uid,
                created_by_username=admin.username,
            ))
            db.commit()

        uploaded = client.post(
            "/api/v1/result-submissions/upload",
            headers={"X-CSRF-Token": csrf},
            files={"file": ("duplicate.ydresult", package, "application/octet-stream")},
        )
        assert uploaded.status_code == 201, uploaded.text
        submission_uid = uploaded.json()["submission_uid"]
        preflight = client.post(
            f"/api/v1/result-submissions/{submission_uid}/preflight",
            headers={"X-CSRF-Token": csrf},
        )
        assert preflight.status_code == 200, preflight.text
        assert preflight.json()["status"] == "conflict"
        assert any(
            item["code"] == "ASSET_POSSIBLE_DUPLICATE"
            for item in preflight.json()["preflight_issues"]
        )
    finally:
        with SessionLocal() as db:
            db.execute(delete(OnlineSurveyEntry).where(OnlineSurveyEntry.entry_uid == web_entry_uid))
            db.commit()
        cleanup_workflow(submission_uid, task_uid, record_uid, asset_uid)
        if batch_uid:
            client.delete(f"/api/v1/survey-batches/{batch_uid}", headers={"X-CSRF-Token": csrf})
        if project_uid:
            client.delete(f"/api/v1/projects/{project_uid}", headers={"X-CSRF-Token": csrf})
        cleanup_test_user(admin.user_uid)


@pytest.fixture
def formal_media_submission():
    admin = create_test_user("admin")
    client = TestClient(app)
    csrf = login_client(client, admin.username)
    project_uid = batch_uid = task_uid = submission_uid = None
    try:
        project_uid, batch_uid, task, scope = create_project_batch_and_task(client, csrf, uuid4().hex[:8], department=True)
        task_uid = task["task_uid"]

        def upload(uid_length=36):
            nonlocal submission_uid
            package, _, _ = make_formal_result_package(
                project_uid=project_uid, batch_uid=batch_uid, task_uid=task_uid, scope=scope,
                record_count=10, media_count=25, media_uid_length=uid_length,
                source_task_uids=(uuid4().hex, uuid4().hex),
            )
            response = client.post("/api/v1/result-submissions/upload", headers={"X-CSRF-Token": csrf},
                                   files={"file": ("media.ydresult", package, "application/octet-stream")})
            assert response.status_code == 201, response.text
            assert response.json()["inspection_error_count"] == 0, response.text
            submission_uid = response.json()["submission_uid"]
            with zipfile.ZipFile(io.BytesIO(package)) as archive:
                documents = {name: json.loads(archive.read(f"data/{name}.json"))["items"]
                             for name in ("engineering_assets", "survey_records", "inspection_results", "survey_media")}
            return submission_uid, documents

        yield client, csrf, task_uid, upload
    finally:
        cleanup_workflow(submission_uid, task_uid, None, None)
        if batch_uid:
            client.delete(f"/api/v1/survey-batches/{batch_uid}", headers={"X-CSRF-Token": csrf})
        if project_uid:
            client.delete(f"/api/v1/projects/{project_uid}", headers={"X-CSRF-Token": csrf})
        cleanup_test_user(admin.user_uid)


def accept_formal(client, csrf, uid):
    headers = {"X-CSRF-Token": csrf}
    preflight = client.post(f"/api/v1/result-submissions/{uid}/preflight", headers=headers)
    assert preflight.status_code == 200, preflight.text
    assert preflight.json()["status"] == "preflight_passed", preflight.text
    reviewed = client.post(f"/api/v1/result-submissions/{uid}/review", headers=headers,
                           json={"decision": "accepted", "notes": "回归审核"})
    assert reviewed.status_code == 200, reviewed.text
    return reviewed.json()


def assert_formal_counts(uid, expected):
    with SessionLocal() as db:
        for model, count in zip((CentralEngineeringAsset, CentralSurveyRecord, CentralInspectionResult, CentralSurveyMedia), expected):
            assert len(list(db.scalars(select(model).where(model.current_submission_uid == uid)))) == count


@pytest.mark.parametrize("uid_length", [36, 32])
def test_formal_ten_records_twenty_five_media(formal_media_submission, uid_length):
    client, csrf, task_uid, upload = formal_media_submission
    uid, documents = upload(uid_length)
    reviewed = accept_formal(client, csrf, uid)
    headers = {"X-CSRF-Token": csrf}
    repeated = client.post(f"/api/v1/result-submissions/{uid}/preflight", headers=headers)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["status"] == "accepted"
    for field in ("reviewed_at", "reviewed_by_username", "review_notes"):
        assert repeated.json()[field] == reviewed[field]
    imported = client.post(f"/api/v1/result-submissions/{uid}/import", headers=headers)
    assert imported.status_code == 200, imported.text
    assert imported.json()["records"] == 10
    assert imported.json()["media"] == 25
    assert_formal_counts(uid, (10, 10, 10, 25))
    with SessionLocal() as db:
        saved_records = {item.survey_record_uid: item for item in db.scalars(
            select(CentralSurveyRecord).where(CentralSurveyRecord.current_submission_uid == uid))}
        for item in documents["survey_records"]:
            assert saved_records[item["survey_record_uid"]].payload_json == item
            assert saved_records[item["survey_record_uid"]].source_task_uid == item["source_task_uid"]
        actual = {item.media_uid: item for item in db.scalars(select(CentralSurveyMedia).where(CentralSurveyMedia.current_submission_uid == uid))}
        for item in documents["survey_media"]:
            saved = actual[item["media_uid"]]
            assert len(saved.media_uid) == uid_length
            for field in ("package_path", "file_sha256", "file_size", "survey_record_uid"):
                assert getattr(saved, field) == item[field]
            assert saved.payload_json == item
        assert db.scalar(select(SurveyTask).where(SurveyTask.task_uid == task_uid)).status == "closed"
    duplicate = client.post(f"/api/v1/result-submissions/{uid}/import", headers=headers)
    assert duplicate.status_code == 409, duplicate.text
    assert_formal_counts(uid, (10, 10, 10, 25))
    assert client.get(f"/api/v1/result-submissions/{uid}").json()["status"] == "imported"


@pytest.mark.parametrize("table", ["central_engineering_assets", "central_survey_records",
                                  "central_inspection_results", "central_survey_media", "survey_tasks"])
def test_formal_database_failure_rolls_back_and_retries(formal_media_submission, table):
    client, csrf, task_uid, upload = formal_media_submission
    uid, _ = upload()
    accept_formal(client, csrf, uid)
    headers = {"X-CSRF-Token": csrf}

    def fail_in_postgres(conn, cursor, statement, parameters, context, executemany):
        verb = "UPDATE" if table == "survey_tasks" else "INSERT INTO"
        if statement.startswith(f"{verb} {table} "):
            # Real PostgreSQL error inside the import transaction, not a mock
            # commit. The media/task cases also exercise late flush failures.
            cursor.execute("SELECT 1 / 0")

    event.listen(engine, "before_cursor_execute", fail_in_postgres)
    try:
        failed = client.post(f"/api/v1/result-submissions/{uid}/import", headers=headers)
    finally:
        event.remove(engine, "before_cursor_execute", fail_in_postgres)
    assert failed.status_code == 500, failed.text
    assert "traceback" not in failed.text.lower()
    assert "division" not in failed.text.lower()
    assert_formal_counts(uid, (0, 0, 0, 0))
    assert client.get(f"/api/v1/result-submissions/{uid}").json()["status"] == "accepted"
    assert client.get(f"/api/v1/survey-tasks/{task_uid}").json()["status"] == "result_received"
    retried = client.post(f"/api/v1/result-submissions/{uid}/import", headers=headers)
    assert retried.status_code == 200, retried.text
    assert_formal_counts(uid, (10, 10, 10, 25))


@pytest.mark.parametrize("operation", ["preflight", "import"])
def test_new_conflict_invalidates_previous_review(formal_media_submission, operation):
    client, csrf, task_uid, upload = formal_media_submission
    uid, _ = upload()
    accept_formal(client, csrf, uid)
    headers = {"X-CSRF-Token": csrf}
    # Cancellation is a real business conflict that can occur after review.
    with SessionLocal() as db:
        task = db.scalar(select(SurveyTask).where(SurveyTask.task_uid == task_uid))
        task.status = "cancelled"
        db.commit()
    response = client.post(f"/api/v1/result-submissions/{uid}/{operation}", headers=headers)
    assert response.status_code == (200 if operation == "preflight" else 409), response.text
    detail = client.get(f"/api/v1/result-submissions/{uid}").json()
    assert detail["status"] == "conflict"
    assert detail["reviewed_at"] is None
    assert detail["reviewed_by_username"] is None
    assert detail["review_notes"] is None
    assert any(issue["code"] == "SUBMISSION_TASK_CANCELLED" for issue in detail["preflight_issues"])
    assert_formal_counts(uid, (0, 0, 0, 0))
    with SessionLocal() as db:
        db.scalar(select(SurveyTask).where(SurveyTask.task_uid == task_uid)).status = "result_received"
        db.commit()
    # The old approval cannot authorize importing once the conflict is fixed.
    assert client.post(f"/api/v1/result-submissions/{uid}/import", headers=headers).status_code == 409
    accept_formal(client, csrf, uid)
    assert client.post(f"/api/v1/result-submissions/{uid}/import", headers=headers).status_code == 200


def test_concurrent_import_requests_are_serialized(formal_media_submission):
    client, csrf, _, upload = formal_media_submission
    uid, _ = upload()
    accept_formal(client, csrf, uid)
    headers = {"X-CSRF-Token": csrf}
    first_writing, second_locking = Event(), Event()

    def coordinate(conn, cursor, statement, parameters, context, executemany):
        if first_writing.is_set() and "result_submissions" in statement and "FOR UPDATE" in statement:
            second_locking.set()
        if statement.startswith("INSERT INTO central_survey_media "):
            first_writing.set()
            assert second_locking.wait(10), "Second request did not reach the submission lock"

    second_client = TestClient(app)
    second_client.cookies.update(client.cookies)

    def second_request():
        assert first_writing.wait(10), "First request did not reach media write"
        return second_client.post(f"/api/v1/result-submissions/{uid}/import", headers=headers)

    event.listen(engine, "before_cursor_execute", coordinate)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(client.post, f"/api/v1/result-submissions/{uid}/import", headers=headers)
            second = pool.submit(second_request)
            assert first.result(timeout=20).status_code == 200
            assert second.result(timeout=20).status_code == 409
    finally:
        event.remove(engine, "before_cursor_execute", coordinate)
        second_client.close()
    assert_formal_counts(uid, (10, 10, 10, 25))
