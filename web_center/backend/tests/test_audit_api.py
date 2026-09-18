from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.main import app
from app.models.audit import AuditEvent
from tests.auth_helpers import (
    cleanup_test_user,
    create_test_user,
    login_client,
)


def test_mutation_is_recorded_and_audit_is_permission_protected() -> None:
    admin = create_test_user("admin")
    viewer = create_test_user("viewer")

    project_uid = None

    try:
        admin_client = TestClient(app)
        admin_csrf = login_client(admin_client, admin.username)

        response = admin_client.post(
            "/api/v1/projects",
            headers={"X-CSRF-Token": admin_csrf},
            json={
                "name": "audit-test-project",
                "status": "active",
            },
        )
        assert response.status_code == 201, response.text
        project_uid = response.json()["project_uid"]

        response = admin_client.get(
            "/api/v1/audit-events",
            params={"resource_type": "projects"},
        )
        assert response.status_code == 200, response.text
        items = response.json()["items"]
        assert any(
            item["actor_username"] == admin.username
            and item["http_method"] == "POST"
            and item["outcome"] == "success"
            for item in items
        )

        viewer_client = TestClient(app)
        login_client(viewer_client, viewer.username)
        response = viewer_client.get("/api/v1/audit-events")
        assert response.status_code == 403

    finally:
        if project_uid is not None:
            admin_client.delete(
                f"/api/v1/projects/{project_uid}",
                headers={"X-CSRF-Token": admin_csrf},
            )
        cleanup_test_user(viewer.user_uid)
        cleanup_test_user(admin.user_uid)
