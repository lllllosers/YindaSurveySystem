from uuid import NAMESPACE_URL, uuid4, uuid5
import shutil

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.main import app
from app.models.central_record import CentralEngineeringAsset, CentralInspectionResult, CentralSurveyMedia, CentralSurveyRecord
from app.models.online_entry import OnlineSurveyEntry
from app.models.survey_task import SurveyTask
from app.services import online_entry_service
from app.services.master_data_service import get_snapshot
from app.services.survey_task_service import BACKEND_ROOT
from tests.auth_helpers import cleanup_test_user, create_test_user, login_client
from tests.test_survey_tasks_api import create_project_and_batch


def test_online_entry_draft_submit_review_and_import() -> None:
    token = uuid4().hex[:8]
    admin = create_test_user("admin")
    client = TestClient(app)
    csrf = login_client(client, admin.username)
    project_uid, batch_uid = create_project_and_batch(client, csrf, token)
    snapshot = get_snapshot()
    scope = snapshot.management_scopes[0]
    office = next(item for item in snapshot.offices if item.master_key == scope.organization_master_key)
    task_uid: str | None = None
    entry_uid: str | None = None
    duplicate_entry_uid: str | None = None

    try:
        task_response = client.post(
            "/api/v1/survey-tasks",
            headers={"X-CSRF-Token": csrf},
            json={
                "project_uid": project_uid,
                "survey_batch_uid": batch_uid,
                "task_name": "Web在线录入闭环测试",
                "target_unit_type": "water_office",
                "target_master_key": office.master_key,
                "selected_management_scope_uids": [scope.stable_uid],
            },
        )
        assert task_response.status_code == 201, task_response.text
        task_uid = task_response.json()["task_uid"]

        definitions_response = client.get("/api/v1/online-entries/form-definitions")
        assert definitions_response.status_code == 200
        definitions = definitions_response.json()
        assert len(definitions) == 14
        definition = definitions[0]
        form_data = {
                field["key"]: ("2026-09" if field["input_type"] == "month" else 1 if field["input_type"] in {"decimal", "signed_decimal", "integer"} else field["choices"][0] if field["choices"] else "自动化测试")
            for field in definition["fields"]
            if field["required"]
        }
        form_data[definition["asset_name_field"]] = "Web在线录入测试对象"
        evaluations = [
            {
                "item_code": item["item_code"],
                "category": item["category"],
                "item_name": item["item_name"],
                "grade": definition["grade_options"][0],
                "description": "自动化测试",
                "remark": "",
            }
            for item in definition["evaluation_items"]
        ]
        create_response = client.post(
            "/api/v1/online-entries",
            headers={"X-CSRF-Token": csrf},
            json={
                "task_uid": task_uid,
                "management_scope_uid": scope.stable_uid,
                "form_code": definition["form_code"],
                "form_data": form_data,
                "evaluations": evaluations,
                "conclusion": {
                    "survey_date": "2026-09-26",
                    "overall_grade": definition["grade_options"][0],
                    "surveyor_signatures": "测试人员",
                    "survey_comment": "Web在线录入闭环验证",
                },
            },
        )
        assert create_response.status_code == 201, create_response.text
        entry_uid = create_response.json()["entry_uid"]
        assert create_response.json()["status"] == "draft"

        media_response = client.post(
            f"/api/v1/online-entries/{entry_uid}/media",
            headers={"X-CSRF-Token": csrf},
            files={"file": ("现场全貌.jpg", b"test-photo-bytes", "image/jpeg")},
            data={"media_role": "现场全貌", "part_name": "进口段"},
        )
        assert media_response.status_code == 201, media_response.text
        media_uid = media_response.json()["media_uid"]
        assert media_response.json()["media_kind"] == "photo"

        submit_response = client.post(
            f"/api/v1/online-entries/{entry_uid}/submit",
            headers={"X-CSRF-Token": csrf},
        )
        assert submit_response.status_code == 200, submit_response.text
        assert submit_response.json()["status"] == "submitted"

        review_response = client.post(
            f"/api/v1/online-entries/{entry_uid}/review",
            headers={"X-CSRF-Token": csrf},
            json={"decision": "accept", "notes": "测试审核通过"},
        )
        assert review_response.status_code == 200, review_response.text
        assert review_response.json()["status"] == "imported"

        record_uid = uuid5(NAMESPACE_URL, f"yinda:web-entry:record:{entry_uid}").hex
        record_response = client.get(f"/api/v1/central-records/{record_uid}")
        assert record_response.status_code == 200, record_response.text
        detail = record_response.json()
        assert detail["asset_name"] == "Web在线录入测试对象"
        assert detail["record_payload"]["source_channel"] == "web_online_entry"
        assert len(detail["inspections"]) == len(evaluations)
        assert len(detail["media"]) == 1
        media_file = client.get(f"/api/v1/central-records/{record_uid}/media/{media_uid}")
        assert media_file.status_code == 200, media_file.text
        assert media_file.content == b"test-photo-bytes"

        duplicate_response = client.post(
            "/api/v1/online-entries",
            headers={"X-CSRF-Token": csrf},
            json={
                "task_uid": task_uid,
                "management_scope_uid": scope.stable_uid,
                "form_code": definition["form_code"],
                "form_data": form_data,
                "evaluations": evaluations,
                "conclusion": {
                    "survey_date": "2026-09-26",
                    "overall_grade": definition["grade_options"][0],
                    "surveyor_signatures": "测试人员",
                    "survey_comment": "重复记录验证",
                },
            },
        )
        assert duplicate_response.status_code == 201, duplicate_response.text
        duplicate_entry_uid = duplicate_response.json()["entry_uid"]
        duplicate_submit = client.post(
            f"/api/v1/online-entries/{duplicate_entry_uid}/submit",
            headers={"X-CSRF-Token": csrf},
        )
        assert duplicate_submit.status_code == 400
        assert "正式成果库中已有同名调查对象" in duplicate_submit.json()["detail"]
    finally:
        if duplicate_entry_uid:
            with SessionLocal() as db:
                db.execute(delete(OnlineSurveyEntry).where(OnlineSurveyEntry.entry_uid == duplicate_entry_uid))
                db.commit()
        if entry_uid:
            asset_uid = uuid5(NAMESPACE_URL, f"yinda:web-entry:asset:{entry_uid}").hex
            record_uid = uuid5(NAMESPACE_URL, f"yinda:web-entry:record:{entry_uid}").hex
            with SessionLocal() as db:
                db.execute(delete(CentralSurveyMedia).where(CentralSurveyMedia.survey_record_uid == record_uid))
                db.execute(delete(CentralInspectionResult).where(CentralInspectionResult.survey_record_uid == record_uid))
                db.execute(delete(CentralSurveyRecord).where(CentralSurveyRecord.survey_record_uid == record_uid))
                db.execute(delete(CentralEngineeringAsset).where(CentralEngineeringAsset.engineering_asset_uid == asset_uid))
                db.execute(delete(OnlineSurveyEntry).where(OnlineSurveyEntry.entry_uid == entry_uid))
                db.commit()
            shutil.rmtree(online_entry_service.ONLINE_MEDIA_ROOT / entry_uid, ignore_errors=True)
        if task_uid:
            with SessionLocal() as db:
                row = db.scalar(select(SurveyTask).where(SurveyTask.task_uid == task_uid))
                if row:
                    directory = (BACKEND_ROOT / row.stored_relative_path).parent
                    db.delete(row)
                    db.commit()
                    shutil.rmtree(directory, ignore_errors=True)
        client.delete(f"/api/v1/survey-batches/{batch_uid}", headers={"X-CSRF-Token": csrf})
        client.delete(f"/api/v1/projects/{project_uid}", headers={"X-CSRF-Token": csrf})
        cleanup_test_user(admin.user_uid)
