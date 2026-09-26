from pathlib import Path
import shutil
import sqlite3
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


def test_register_existing_desktop_task_is_idempotent(tmp_path: Path) -> None:
    token = uuid4().hex[:8]
    admin = create_test_user("admin")
    client = TestClient(app)
    csrf = login_client(client, admin.username)
    project_uid, batch_uid = create_project_and_batch(client, csrf, token)
    snapshot = get_snapshot()
    scope = snapshot.management_scopes[0]
    office = next(item for item in snapshot.offices if item.master_key == scope.organization_master_key)
    task_uid: str | None = None
    try:
        created = client.post(
            "/api/v1/survey-tasks",
            headers={"X-CSRF-Token": csrf},
            json={
                "project_uid": project_uid,
                "survey_batch_uid": batch_uid,
                "task_name": "既有桌面任务接续测试",
                "target_unit_type": "water_office",
                "target_master_key": office.master_key,
                "selected_management_scope_uids": [scope.stable_uid],
            },
        )
        assert created.status_code == 201, created.text
        task_uid = created.json()["task_uid"]
        package = client.get(f"/api/v1/survey-tasks/{task_uid}/download")
        assert package.status_code == 200
        package_bytes = package.content

        with SessionLocal() as db:
            row = db.scalar(select(SurveyTask).where(SurveyTask.task_uid == task_uid))
            assert row is not None
            directory = (BACKEND_ROOT / row.stored_relative_path).parent
            db.delete(row)
            db.commit()
        shutil.rmtree(directory, ignore_errors=True)

        imported = client.post(
            "/api/v1/survey-tasks/import-existing",
            headers={"X-CSRF-Token": csrf},
            files={"file": ("original-task.ydtask", package_bytes, "application/zip")},
        )
        assert imported.status_code == 201, imported.text
        detail = imported.json()
        assert detail["task_uid"] == task_uid
        assert detail["source_channel"] == "desktop_handover"
        assert detail["source_filename"] == "original-task.ydtask"
        assert detail["status"] == "downloaded"

        repeated = client.post(
            "/api/v1/survey-tasks/import-existing",
            headers={"X-CSRF-Token": csrf},
            files={"file": ("original-task.ydtask", package_bytes, "application/zip")},
        )
        assert repeated.status_code == 201, repeated.text
        assert repeated.json()["task_uid"] == task_uid
        assert client.get("/api/v1/survey-tasks").json()["items"][0]["source_channel"] in {
            "desktop_handover", "web_center"
        }
    finally:
        if task_uid:
            cleanup_task(task_uid)
        client.delete(f"/api/v1/survey-batches/{batch_uid}", headers={"X-CSRF-Token": csrf})
        client.delete(f"/api/v1/projects/{project_uid}", headers={"X-CSRF-Token": csrf})
        cleanup_test_user(admin.user_uid)


def test_handover_issued_tasks_from_read_only_desktop_database(tmp_path: Path) -> None:
    from services.survey_task_package_reader import inspect_survey_task_package

    admin = create_test_user("admin")
    manager = create_test_user("manager")
    client = TestClient(app)
    manager_client = TestClient(app)
    csrf = login_client(client, admin.username)
    manager_csrf = login_client(manager_client, manager.username)
    source = tmp_path / "desktop-center-backup.db"
    task_uid = uuid4().hex
    package_uid = uuid4().hex
    project_uid = uuid4().hex
    batch_uid = uuid4().hex
    department_uid = uuid4().hex
    office_uid = uuid4().hex
    parent_canal_uid = uuid4().hex
    canal_uid = uuid4().hex
    scope_uid = uuid4().hex

    with sqlite3.connect(source) as connection:
        connection.executescript(
            """
            CREATE TABLE survey_task_issues (
                id INTEGER PRIMARY KEY,
                task_uid TEXT NOT NULL,
                source_package_uid TEXT NOT NULL,
                task_schema_version TEXT NOT NULL,
                app_version TEXT NOT NULL,
                parent_task_uid TEXT,
                root_task_uid TEXT,
                task_depth INTEGER NOT NULL,
                target_unit_type TEXT NOT NULL,
                project_uid TEXT NOT NULL,
                project_name_snapshot TEXT NOT NULL,
                project_short_name_snapshot TEXT,
                survey_batch_uid TEXT NOT NULL,
                batch_name_snapshot TEXT NOT NULL,
                batch_code_snapshot TEXT NOT NULL,
                batch_start_date_snapshot TEXT,
                batch_end_date_snapshot TEXT,
                department_uid TEXT NOT NULL,
                department_name_snapshot TEXT NOT NULL,
                organization_unit_uid TEXT NOT NULL,
                organization_name_snapshot TEXT NOT NULL,
                task_name TEXT NOT NULL,
                notes TEXT,
                selected_scope_count INTEGER NOT NULL,
                task_created_at TEXT NOT NULL,
                issued_at TEXT NOT NULL
            );
            CREATE TABLE survey_task_issue_scopes (
                id INTEGER PRIMARY KEY,
                task_issue_id INTEGER NOT NULL,
                management_scope_uid TEXT NOT NULL,
                canal_unit_uid TEXT NOT NULL,
                organization_unit_uid TEXT NOT NULL,
                canal_name_snapshot TEXT NOT NULL,
                canal_level_snapshot TEXT NOT NULL,
                range_mode TEXT NOT NULL,
                start_stake_text TEXT,
                start_stake_value REAL,
                end_stake_text TEXT,
                end_stake_value REAL,
                sort_order INTEGER NOT NULL,
                source_scope_status TEXT NOT NULL,
                description TEXT
            );
            CREATE TABLE organization_units (
                id INTEGER PRIMARY KEY,
                parent_id INTEGER,
                name TEXT NOT NULL,
                unit_type TEXT NOT NULL,
                business_code TEXT,
                status TEXT NOT NULL,
                description TEXT,
                sort_order INTEGER NOT NULL,
                organization_unit_uid TEXT NOT NULL
            );
            CREATE TABLE canal_units (
                id INTEGER PRIMARY KEY,
                parent_id INTEGER,
                name TEXT NOT NULL,
                canal_level TEXT NOT NULL,
                status TEXT NOT NULL,
                description TEXT,
                sort_order INTEGER NOT NULL,
                canal_unit_uid TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO organization_units VALUES (1, NULL, ?, 'department', 'D01', 'active', NULL, 1, ?)",
            ("第一管理处", department_uid),
        )
        connection.execute(
            "INSERT INTO organization_units VALUES (2, 1, ?, 'water_office', 'O01', 'active', NULL, 2, ?)",
            ("第一水管所", office_uid),
        )
        connection.execute(
            "INSERT INTO canal_units VALUES (1, NULL, ?, '01', 'active', NULL, 1, ?)",
            ("总干渠", parent_canal_uid),
        )
        connection.execute(
            "INSERT INTO canal_units VALUES (2, 1, ?, '02', 'active', NULL, 2, ?)",
            ("一干渠", canal_uid),
        )
        connection.execute(
            """
            INSERT INTO survey_task_issues VALUES (
                1, ?, ?, '3.0', '1.2.0', NULL, ?, 0, 'water_office',
                ?, '历史项目', '历史项目', ?, '历史批次', 'HISTORY-2026',
                '2026-01-01', '2026-12-31', ?, '第一管理处', ?, '第一水管所',
                '桌面端正式下发任务', '从不可变历史接续', 1,
                '2026-09-01T09:00:00+08:00', '2026-09-01 09:00:00'
            )
            """,
            (task_uid, package_uid, task_uid, project_uid, batch_uid, department_uid, office_uid),
        )
        connection.execute(
            """
            INSERT INTO survey_task_issue_scopes VALUES (
                1, 1, ?, ?, ?, '一干渠', '02', 'segment_known',
                '0+000', 0.0, '1+000', 1000.0, 1, 'active', '历史冻结范围'
            )
            """,
            (scope_uid, canal_uid, office_uid),
        )

    task_created = False
    try:
        database_bytes = source.read_bytes()
        forbidden = manager_client.post(
            "/api/v1/survey-tasks/handover-desktop-database",
            headers={"X-CSRF-Token": manager_csrf},
            files={"file": (source.name, database_bytes, "application/vnd.sqlite3")},
        )
        assert forbidden.status_code == 403

        imported = client.post(
            "/api/v1/survey-tasks/handover-desktop-database",
            headers={"X-CSRF-Token": csrf},
            files={"file": (source.name, database_bytes, "application/vnd.sqlite3")},
        )
        assert imported.status_code == 200, imported.text
        report = imported.json()
        assert report["discovered_tasks"] == 1
        assert report["imported_tasks"] == 1
        assert report["existing_tasks"] == 0
        assert report["conflict_tasks"] == 0
        assert report["created_projects"] == 1
        assert report["created_batches"] == 1
        task_created = True

        detail = client.get(f"/api/v1/survey-tasks/{task_uid}")
        assert detail.status_code == 200
        assert detail.json()["source_channel"] == "desktop_handover"
        assert detail.json()["source_filename"] == source.name
        assert detail.json()["selected_scope_count"] == 1
        assert detail.json()["frozen_scopes"][0]["canal_name"] == "一干渠"

        package = client.get(f"/api/v1/survey-tasks/{task_uid}/download")
        assert package.status_code == 200
        package_path = tmp_path / "recovered.ydtask"
        package_path.write_bytes(package.content)
        inspection = inspect_survey_task_package(package_path)
        assert inspection.valid, inspection.format_text()
        assert inspection.task is not None
        assert inspection.task["task_uid"] == task_uid
        assert len(inspection.canals) == 2

        repeated = client.post(
            "/api/v1/survey-tasks/handover-desktop-database",
            headers={"X-CSRF-Token": csrf},
            files={"file": (source.name, database_bytes, "application/vnd.sqlite3")},
        )
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["imported_tasks"] == 0
        assert repeated.json()["existing_tasks"] == 1
    finally:
        if task_created:
            cleanup_task(task_uid)
        client.delete(f"/api/v1/survey-batches/{batch_uid}", headers={"X-CSRF-Token": csrf})
        client.delete(f"/api/v1/projects/{project_uid}", headers={"X-CSRF-Token": csrf})
        cleanup_test_user(manager.user_uid)
        cleanup_test_user(admin.user_uid)


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
