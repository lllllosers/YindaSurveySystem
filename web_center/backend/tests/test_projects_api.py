from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_project_and_batch_crud_round_trip() -> None:
    token = uuid4().hex[:10]
    project_uid: str | None = None
    batch_uid: str | None = None

    try:
        response = client.post(
            "/api/v1/projects",
            json={
                "name": f"测试项目-{token}",
                "short_name": f"T-{token}",
                "status": "active",
            },
        )
        assert response.status_code == 201, response.text
        project = response.json()
        project_uid = project["project_uid"]

        response = client.get("/api/v1/projects")
        assert response.status_code == 200
        assert any(
            item["project_uid"] == project_uid
            for item in response.json()
        )

        response = client.patch(
            f"/api/v1/projects/{project_uid}",
            json={"short_name": f"T2-{token}"},
        )
        assert response.status_code == 200, response.text

        response = client.post(
            f"/api/v1/projects/{project_uid}/batches",
            json={
                "batch_name": f"测试批次-{token}",
                "batch_code": f"B-{token}",
                "start_date": "2026-09-01",
                "end_date": "2026-12-31",
                "status": "planned",
            },
        )
        assert response.status_code == 201, response.text
        batch = response.json()
        batch_uid = batch["survey_batch_uid"]

        response = client.get(
            f"/api/v1/projects/{project_uid}/batches"
        )
        assert response.status_code == 200, response.text
        assert any(
            item["survey_batch_uid"] == batch_uid
            for item in response.json()
        )

        response = client.patch(
            f"/api/v1/survey-batches/{batch_uid}",
            json={"status": "active"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "active"

        blocked = client.delete(f"/api/v1/projects/{project_uid}")
        assert blocked.status_code == 409

    finally:
        if batch_uid is not None:
            client.delete(f"/api/v1/survey-batches/{batch_uid}")
        if project_uid is not None:
            client.delete(f"/api/v1/projects/{project_uid}")
