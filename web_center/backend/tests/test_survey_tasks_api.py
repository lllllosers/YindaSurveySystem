from pathlib import Path
import shutil
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.survey_task import SurveyTask
from app.models.master_data import MasterDataState, MasterManagementScope
from app.services.master_data_service import get_snapshot
from app.services.survey_task_service import BACKEND_ROOT
from tests.auth_helpers import cleanup_test_user, create_test_user, login_client


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DESKTOP_SRC = REPOSITORY_ROOT / "src"
if str(DESKTOP_SRC) not in sys.path:
    sys.path.insert(0, str(DESKTOP_SRC))


def cleanup_task(task_uid: str) -> None:
    with SessionLocal() as db:
        row = db.scalar(select(SurveyTask).where(SurveyTask.task_uid == task_uid))
        if row is None:
            return
        directory = (BACKEND_ROOT / row.stored_relative_path).parent
        db.delete(row)
        db.commit()
        shutil.rmtree(directory, ignore_errors=True)


def create_project_and_batch(client: TestClient, csrf: str, token: str) -> tuple[str, str]:
    project = client.post(
        "/api/v1/projects",
        headers={"X-CSRF-Token": csrf},
        json={"name": f"任务测试项目-{token}", "short_name": "任务测试", "status": "active"},
    )
    assert project.status_code == 201, project.text
    project_uid = project.json()["project_uid"]
    batch = client.post(
        f"/api/v1/projects/{project_uid}/batches",
        headers={"X-CSRF-Token": csrf},
        json={
            "batch_name": f"任务测试批次-{token}",
            "batch_code": f"TASK-{token}",
            "start_date": "2026-09-01",
            "end_date": "2026-12-31",
            "status": "active",
        },
    )
    assert batch.status_code == 201, batch.text
    return project_uid, batch.json()["survey_batch_uid"]


def test_create_download_and_validate_desktop_v3_task_package(tmp_path: Path) -> None:
    from services.survey_task_package_reader import inspect_survey_task_package

    token = uuid4().hex[:8]
    admin = create_test_user("admin")
    client = TestClient(app)
    csrf = login_client(client, admin.username)
    project_uid, batch_uid = create_project_and_batch(client, csrf, token)
    snapshot = get_snapshot()
    scope = snapshot.management_scopes[0]
    office = next(
        item for item in snapshot.offices
        if item.master_key == scope.organization_master_key
    )
    task_uid: str | None = None

    try:
        response = client.post(
            "/api/v1/survey-tasks",
            headers={"X-CSRF-Token": csrf},
            json={
                "project_uid": project_uid,
                "survey_batch_uid": batch_uid,
                "task_name": "桌面兼容任务包测试",
                "notes": "由 Web 中心生成",
                "target_unit_type": "water_office",
                "target_master_key": office.master_key,
                "selected_management_scope_uids": [scope.stable_uid],
            },
        )
        assert response.status_code == 201, response.text
        detail = response.json()
        task_uid = detail["task_uid"]
        assert detail["task_depth"] == 0
        assert detail["root_task_uid"] == task_uid
        assert detail["parent_task_uid"] is None
        assert detail["selected_scope_count"] == 1
        assert detail["form_count"] == 14
        assert detail["status"] == "issued"

        package_response = client.get(f"/api/v1/survey-tasks/{task_uid}/download")
        assert package_response.status_code == 200, package_response.text
        package_path = tmp_path / "web-generated.ydtask"
        package_path.write_bytes(package_response.content)

        inspection = inspect_survey_task_package(package_path)
        assert inspection.valid, inspection.format_text()
        assert inspection.task is not None
        assert inspection.task["task_uid"] == task_uid
        assert inspection.task["assignment"]["organization_unit_uid"] == office.stable_uid
        assert inspection.task["scope"]["selected_management_scope_uids"] == [scope.stable_uid]
        assert len(inspection.forms) == 14

        detail_response = client.get(f"/api/v1/survey-tasks/{task_uid}")
        assert detail_response.status_code == 200
        assert detail_response.json()["status"] == "downloaded"
        assert detail_response.json()["download_count"] == 1
    finally:
        if task_uid:
            cleanup_task(task_uid)
        client.delete(
            f"/api/v1/survey-batches/{batch_uid}",
            headers={"X-CSRF-Token": csrf},
        )
        client.delete(
            f"/api/v1/projects/{project_uid}",
            headers={"X-CSRF-Token": csrf},
        )
        cleanup_test_user(admin.user_uid)


def test_task_permissions_and_target_scope_authority() -> None:
    token = uuid4().hex[:8]
    admin = create_test_user("admin")
    viewer = create_test_user("viewer")
    admin_client = TestClient(app)
    viewer_client = TestClient(app)
    admin_csrf = login_client(admin_client, admin.username)
    viewer_csrf = login_client(viewer_client, viewer.username)
    project_uid, batch_uid = create_project_and_batch(admin_client, admin_csrf, token)
    snapshot = get_snapshot()
    first_scope = snapshot.management_scopes[0]
    other_scope = next(
        item for item in snapshot.management_scopes
        if item.organization_master_key != first_scope.organization_master_key
    )
    office = next(
        item for item in snapshot.offices
        if item.master_key == first_scope.organization_master_key
    )
    payload = {
        "project_uid": project_uid,
        "survey_batch_uid": batch_uid,
        "task_name": "权限测试",
        "target_unit_type": "water_office",
        "target_master_key": office.master_key,
        "selected_management_scope_uids": [other_scope.stable_uid],
    }
    try:
        forbidden = viewer_client.post(
            "/api/v1/survey-tasks",
            headers={"X-CSRF-Token": viewer_csrf},
            json=payload,
        )
        assert forbidden.status_code == 403
        invalid_scope = admin_client.post(
            "/api/v1/survey-tasks",
            headers={"X-CSRF-Token": admin_csrf},
            json=payload,
        )
        assert invalid_scope.status_code == 400
        assert "不属于任务目标单位" in invalid_scope.json()["detail"]
        readable = viewer_client.get("/api/v1/survey-tasks")
        assert readable.status_code == 200
    finally:
        admin_client.delete(
            f"/api/v1/survey-batches/{batch_uid}",
            headers={"X-CSRF-Token": admin_csrf},
        )
        admin_client.delete(
            f"/api/v1/projects/{project_uid}",
            headers={"X-CSRF-Token": admin_csrf},
        )
        cleanup_test_user(viewer.user_uid)
        cleanup_test_user(admin.user_uid)


def test_form_contract_matches_desktop_registry() -> None:
    from forms.engineering.registry import get_engineering_form_definitions
    from app.services.survey_task_service import load_form_contract

    items, version, contract_hash = load_form_contract()
    desktop = get_engineering_form_definitions()
    assert version == "2026-09-v1.2.0"
    assert len(contract_hash) == 64
    assert [item["form_code"] for item in items] == [item.form_code for item in desktop]
    assert [item["form_number"] for item in items] == [item.form_number for item in desktop]
    assert [item["form_name"] for item in items] == [item.form_name for item in desktop]
    assert [item["asset_type"] for item in items] == [item.asset_type for item in desktop]


def test_issued_task_keeps_master_snapshot_while_new_task_uses_latest_version() -> None:
    token = uuid4().hex[:8]
    admin = create_test_user("admin")
    client = TestClient(app)
    csrf = login_client(client, admin.username)
    project_uid, batch_uid = create_project_and_batch(client, csrf, token)
    snapshot = get_snapshot()
    scope = snapshot.management_scopes[0]
    office = next(
        item for item in snapshot.offices
        if item.master_key == scope.organization_master_key
    )
    task_uids: list[str] = []
    with SessionLocal() as db:
        state = db.get(MasterDataState, 1)
        scope_row = db.scalar(
            select(MasterManagementScope).where(
                MasterManagementScope.stable_uid == scope.stable_uid
            )
        )
        assert state is not None and scope_row is not None
        original_revision = state.revision_no
        original_description = scope_row.description

    def create_named_task(name: str):
        response = client.post(
            "/api/v1/survey-tasks",
            headers={"X-CSRF-Token": csrf},
            json={
                "project_uid": project_uid,
                "survey_batch_uid": batch_uid,
                "task_name": name,
                "target_unit_type": "water_office",
                "target_master_key": office.master_key,
                "selected_management_scope_uids": [scope.stable_uid],
            },
        )
        assert response.status_code == 201, response.text
        task_uids.append(response.json()["task_uid"])
        return response.json()

    try:
        first = create_named_task("资料冻结验证任务一")
        first_version = first["master_data_version"]

        with SessionLocal() as db:
            state = db.get(MasterDataState, 1)
            scope_row = db.scalar(
                select(MasterManagementScope).where(
                    MasterManagementScope.stable_uid == scope.stable_uid
                )
            )
            assert state is not None and scope_row is not None
            scope_row.description = f"自动化版本验证-{token}"
            state.revision_no += 1
            db.commit()

        old_detail = client.get(f"/api/v1/survey-tasks/{first['task_uid']}")
        assert old_detail.status_code == 200
        assert old_detail.json()["master_data_version"] == first_version

        second = create_named_task("资料冻结验证任务二")
        assert second["master_data_version"] != first_version
        assert second["master_data_version"] == get_snapshot().summary.master_data_version
    finally:
        for task_uid in task_uids:
            cleanup_task(task_uid)
        client.delete(
            f"/api/v1/survey-batches/{batch_uid}",
            headers={"X-CSRF-Token": csrf},
        )
        client.delete(
            f"/api/v1/projects/{project_uid}",
            headers={"X-CSRF-Token": csrf},
        )
        with SessionLocal() as db:
            state = db.get(MasterDataState, 1)
            scope_row = db.scalar(
                select(MasterManagementScope).where(
                    MasterManagementScope.stable_uid == scope.stable_uid
                )
            )
            assert state is not None and scope_row is not None
            scope_row.description = original_description
            state.revision_no = original_revision
            db.commit()
        cleanup_test_user(admin.user_uid)
