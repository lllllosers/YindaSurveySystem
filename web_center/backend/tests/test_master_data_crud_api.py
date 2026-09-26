from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.main import app
from app.models.master_data import MasterCanal, MasterDataState, MasterDepartment, MasterManagementScope, MasterOffice
from tests.auth_helpers import cleanup_test_user, create_test_user, login_client


def test_master_data_crud_split_scope_and_permissions() -> None:
    token = uuid4().hex[:8]
    manager = create_test_user("manager")
    viewer = create_test_user("viewer")
    client = TestClient(app)
    viewer_client = TestClient(app)
    csrf = login_client(client, manager.username)
    viewer_csrf = login_client(viewer_client, viewer.username)
    created: dict[str, list[str]] = {"departments": [], "offices": [], "canals": [], "scopes": []}
    with SessionLocal() as db:
        original_revision = db.get(MasterDataState, 1).revision_no

    try:
        forbidden = viewer_client.post(
            "/api/v1/master-data/departments",
            headers={"X-CSRF-Token": viewer_csrf},
            json={"name": "无权限新增", "business_code": f"NO-{token}", "sort_order": 999, "description": None},
        )
        assert forbidden.status_code == 403

        department = client.post(
            "/api/v1/master-data/departments",
            headers={"X-CSRF-Token": csrf},
            json={"name": f"测试管理处-{token}", "business_code": f"D-{token}", "sort_order": 9000, "description": "测试后删除"},
        )
        assert department.status_code == 201, department.text
        department_uid = department.json()["stable_uid"]
        created["departments"].append(department_uid)

        office_uids = []
        for index in (1, 2):
            response = client.post(
                "/api/v1/master-data/offices",
                headers={"X-CSRF-Token": csrf},
                json={"name": f"测试管理所{index}-{token}", "business_code": f"{index}-{token}", "parent_department_uid": department_uid, "sort_order": 9000 + index, "description": None},
            )
            assert response.status_code == 201, response.text
            office_uids.append(response.json()["stable_uid"])
            created["offices"].append(response.json()["stable_uid"])

        canal = client.post(
            "/api/v1/master-data/canals",
            headers={"X-CSRF-Token": csrf},
            json={"name": f"测试分段渠道-{token}", "canal_level": "01", "parent_canal_uid": None, "sort_order": 9000, "description": None},
        )
        assert canal.status_code == 201, canal.text
        canal_uid = canal.json()["stable_uid"]
        created["canals"].append(canal_uid)

        for office_uid, start, end in ((office_uids[0], "CH0+000", "CH10+000"), (office_uids[1], "CH10+000", "CH20+000")):
            response = client.post(
                "/api/v1/master-data/scopes",
                headers={"X-CSRF-Token": csrf},
                json={"canal_uid": canal_uid, "organization_unit_uid": office_uid, "range_mode": "segment_known", "start_stake_text": start, "end_stake_text": end, "sort_order": 9000, "description": None},
            )
            assert response.status_code == 201, response.text
            created["scopes"].append(response.json()["stable_uid"])

        overlap = client.post(
            "/api/v1/master-data/scopes",
            headers={"X-CSRF-Token": csrf},
            json={"canal_uid": canal_uid, "organization_unit_uid": office_uids[0], "range_mode": "segment_known", "start_stake_text": "CH5+000", "end_stake_text": "CH15+000", "sort_order": 9001, "description": None},
        )
        assert overlap.status_code == 400
        assert "重叠" in overlap.json()["detail"]

        cannot_stop = client.post(
            f"/api/v1/master-data/canals/{canal_uid}/status",
            headers={"X-CSRF-Token": csrf}, json={"status": "inactive"},
        )
        assert cannot_stop.status_code == 400
        assert "分管范围" in cannot_stop.json()["detail"]

        for scope_uid in list(created["scopes"]):
            assert client.post(f"/api/v1/master-data/scopes/{scope_uid}/status", headers={"X-CSRF-Token": csrf}, json={"status": "inactive"}).status_code == 200
            assert client.delete(f"/api/v1/master-data/scopes/{scope_uid}", headers={"X-CSRF-Token": csrf}).status_code == 204
            created["scopes"].remove(scope_uid)
        assert client.post(f"/api/v1/master-data/canals/{canal_uid}/status", headers={"X-CSRF-Token": csrf}, json={"status": "inactive"}).status_code == 200
        assert client.delete(f"/api/v1/master-data/canals/{canal_uid}", headers={"X-CSRF-Token": csrf}).status_code == 204
        created["canals"].remove(canal_uid)
        for office_uid in list(created["offices"]):
            assert client.post(f"/api/v1/master-data/offices/{office_uid}/status", headers={"X-CSRF-Token": csrf}, json={"status": "inactive"}).status_code == 200
            assert client.delete(f"/api/v1/master-data/offices/{office_uid}", headers={"X-CSRF-Token": csrf}).status_code == 204
            created["offices"].remove(office_uid)
        assert client.post(f"/api/v1/master-data/departments/{department_uid}/status", headers={"X-CSRF-Token": csrf}, json={"status": "inactive"}).status_code == 200
        assert client.delete(f"/api/v1/master-data/departments/{department_uid}", headers={"X-CSRF-Token": csrf}).status_code == 204
        created["departments"].remove(department_uid)
    finally:
        with SessionLocal() as db:
            db.execute(delete(MasterManagementScope).where(MasterManagementScope.stable_uid.in_(created["scopes"])))
            db.execute(delete(MasterCanal).where(MasterCanal.stable_uid.in_(created["canals"])))
            db.execute(delete(MasterOffice).where(MasterOffice.stable_uid.in_(created["offices"])))
            db.execute(delete(MasterDepartment).where(MasterDepartment.stable_uid.in_(created["departments"])))
            state = db.get(MasterDataState, 1)
            state.revision_no = original_revision
            db.commit()
        cleanup_test_user(viewer.user_uid)
        cleanup_test_user(manager.user_uid)
