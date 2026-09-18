from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import (
    cleanup_test_user,
    create_test_user,
    login_client,
)


def test_project_and_batch_crud_round_trip() -> None:
    token = uuid4().hex[:10]
    admin = create_test_user("admin")
    client = TestClient(app)
    csrf = login_client(client, admin.username)

    project_uid: str | None = None
    batch_uid: str | None = None

    try:
        response = client.post(
            "/api/v1/projects",
            headers={"X-CSRF-Token": csrf},
            json={
                "name": f"测试项目-{token}",
                "short_name": f"T-{token}",
                "status": "active",
            },
        )
        assert response.status_code == 201, response.text
        project_uid = response.json()["project_uid"]

        response = client.get("/api/v1/projects")
        assert response.status_code == 200
        assert any(
            item["project_uid"] == project_uid
            for item in response.json()
        )

        response = client.patch(
            f"/api/v1/projects/{project_uid}",
            headers={"X-CSRF-Token": csrf},
            json={"short_name": f"T2-{token}"},
        )
        assert response.status_code == 200, response.text

        response = client.post(
            f"/api/v1/projects/{project_uid}/batches",
            headers={"X-CSRF-Token": csrf},
            json={
                "batch_name": f"测试批次-{token}",
                "batch_code": f"B-{token}",
                "start_date": "2026-09-01",
                "end_date": "2026-12-31",
                "status": "planned",
            },
        )
        assert response.status_code == 201, response.text
        batch_uid = response.json()["survey_batch_uid"]

        response = client.patch(
            f"/api/v1/survey-batches/{batch_uid}",
            headers={"X-CSRF-Token": csrf},
            json={"status": "active"},
        )
        assert response.status_code == 200, response.text

        blocked = client.delete(
            f"/api/v1/projects/{project_uid}",
            headers={"X-CSRF-Token": csrf},
        )
        assert blocked.status_code == 409

    finally:
        if batch_uid is not None:
            client.delete(
                f"/api/v1/survey-batches/{batch_uid}",
                headers={"X-CSRF-Token": csrf},
            )
        if project_uid is not None:
            client.delete(
                f"/api/v1/projects/{project_uid}",
                headers={"X-CSRF-Token": csrf},
            )
        cleanup_test_user(admin.user_uid)
