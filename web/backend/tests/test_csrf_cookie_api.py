from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.auth_helpers import (
    cleanup_test_user,
    create_test_user,
)


TEST_PASSWORD = "TestPassword-2026!"


def test_csrf_cookie_rotates_and_is_shared_by_browser_scope() -> None:
    admin = create_test_user("admin")
    project_uid = None

    try:
        client = TestClient(app)

        login = client.post(
            "/api/v1/auth/login",
            json={
                "username": admin.username,
                "password": TEST_PASSWORD,
            },
        )
        assert login.status_code == 200, login.text

        old_token = login.json()["csrf_token"]
        assert client.cookies.get("yd_csrf") == old_token

        refreshed = client.get(
            "/api/v1/auth/csrf"
        )
        assert refreshed.status_code == 200, refreshed.text

        new_token = refreshed.json()["csrf_token"]
        assert new_token != old_token
        assert client.cookies.get("yd_csrf") == new_token

        stale = client.post(
            "/api/v1/projects",
            headers={
                "X-CSRF-Token": old_token,
            },
            json={
                "name": (
                    "csrf-stale-"
                    + uuid4().hex[:8]
                ),
                "status": "active",
            },
        )
        assert stale.status_code == 403

        created = client.post(
            "/api/v1/projects",
            headers={
                "X-CSRF-Token": new_token,
            },
            json={
                "name": (
                    "csrf-current-"
                    + uuid4().hex[:8]
                ),
                "status": "active",
            },
        )
        assert created.status_code == 201, created.text
        project_uid = created.json()["project_uid"]

        deleted = client.delete(
            f"/api/v1/projects/{project_uid}",
            headers={
                "X-CSRF-Token": new_token,
            },
        )
        assert deleted.status_code == 204
        project_uid = None

        logout = client.post(
            "/api/v1/auth/logout",
            headers={
                "X-CSRF-Token": new_token,
            },
        )
        assert logout.status_code == 204
        assert client.cookies.get("yd_session") is None
        assert client.cookies.get("yd_csrf") is None

    finally:
        if project_uid is not None:
            # Normally unreachable because the created project is deleted
            # in the successful path. Cleanup remains defensive.
            with TestClient(app) as cleanup_client:
                relogin = cleanup_client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": admin.username,
                        "password": TEST_PASSWORD,
                    },
                )
                if relogin.status_code == 200:
                    token = relogin.json()["csrf_token"]
                    cleanup_client.delete(
                        f"/api/v1/projects/{project_uid}",
                        headers={
                            "X-CSRF-Token": token,
                        },
                    )

        cleanup_test_user(admin.user_uid)
