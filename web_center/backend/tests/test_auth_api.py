from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import (
    cleanup_test_user,
    create_test_user,
    login_client,
)


def test_authentication_and_role_authorization() -> None:
    viewer = create_test_user("viewer")
    admin = create_test_user("admin")

    try:
        anonymous = TestClient(app)
        assert anonymous.get("/api/v1/projects").status_code == 401

        viewer_client = TestClient(app)
        viewer_csrf = login_client(viewer_client, viewer.username)
        me = viewer_client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["role"] == "viewer"
        assert viewer_client.get("/api/v1/projects").status_code == 200

        denied = viewer_client.post(
            "/api/v1/projects",
            headers={"X-CSRF-Token": viewer_csrf},
            json={"name": "viewer cannot create", "status": "active"},
        )
        assert denied.status_code == 403

        admin_client = TestClient(app)
        admin_csrf = login_client(admin_client, admin.username)
        assert admin_client.get("/api/v1/users").status_code == 200

        created = admin_client.post(
            "/api/v1/projects",
            headers={"X-CSRF-Token": admin_csrf},
            json={"name": "auth-test-project", "status": "active"},
        )
        assert created.status_code == 201, created.text
        project_uid = created.json()["project_uid"]

        deleted = admin_client.delete(
            f"/api/v1/projects/{project_uid}",
            headers={"X-CSRF-Token": admin_csrf},
        )
        assert deleted.status_code == 204

    finally:
        cleanup_test_user(viewer.user_uid)
        cleanup_test_user(admin.user_uid)


def test_csrf_required_for_mutation() -> None:
    admin = create_test_user("admin")
    try:
        client = TestClient(app)
        login_client(client, admin.username)
        response = client.post(
            "/api/v1/projects",
            json={"name": "csrf-test-project", "status": "active"},
        )
        assert response.status_code == 403
    finally:
        cleanup_test_user(admin.user_uid)
