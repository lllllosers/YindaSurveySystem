from fastapi.testclient import TestClient
from sqlalchemy import select
from uuid import uuid4

from app.db.session import SessionLocal
from app.main import app
from app.models.auth import RegistrationInvite, User
from app.services.master_data_service import get_snapshot
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


def test_public_registration_requires_admin_approval() -> None:
    username = f"registration-{uuid4().hex[:12]}"
    registered_uid: str | None = None
    admin = create_test_user("admin")
    anonymous = TestClient(app)

    try:
        response = anonymous.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "display_name": "Registration Applicant",
                "password": "TestPassword-2026!",
                "role": "admin",
                "is_active": True,
            },
        )
        assert response.status_code == 201, response.text

        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.username == username))
            assert user is not None
            registered_uid = user.user_uid
            assert user.role == "viewer"
            assert user.is_active is False
            assert user.is_approved is False

        assert anonymous.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "TestPassword-2026!"},
        ).status_code == 401
        assert anonymous.post(
            "/api/v1/auth/register",
            json={"username": username, "display_name": "Duplicate", "password": "TestPassword-2026!"},
        ).status_code == 409

        admin_client = TestClient(app)
        csrf = login_client(admin_client, admin.username)
        pending = admin_client.get("/api/v1/users")
        assert pending.status_code == 200
        assert any(row["user_uid"] == registered_uid and not row["is_approved"] for row in pending.json())
        pending_overview = admin_client.get("/api/v1/overview")
        assert pending_overview.status_code == 200
        pending_count = pending_overview.json()["pending_user_count"]
        assert pending_count >= 1

        approved = admin_client.patch(
            f"/api/v1/users/{registered_uid}",
            headers={"X-CSRF-Token": csrf},
            json={"is_active": True},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["is_approved"] is True
        assert admin_client.get("/api/v1/overview").json()["pending_user_count"] == pending_count - 1

        viewer_client = TestClient(app)
        login_client(viewer_client, username)
        assert viewer_client.get("/api/v1/projects").status_code == 200
        assert viewer_client.get("/api/v1/users").status_code == 403
        assert viewer_client.get("/api/v1/overview").json()["pending_user_count"] == 0
    finally:
        if registered_uid:
            cleanup_test_user(registered_uid)
        cleanup_test_user(admin.user_uid)


def test_batch_approval_is_atomic_and_assigns_one_role() -> None:
    admin = create_test_user("admin")
    client = TestClient(app)
    csrf = login_client(client, admin.username)
    registered_uids: list[str] = []

    try:
        for _ in range(2):
            username = f"batch-{uuid4().hex[:12]}"
            response = TestClient(app).post(
                "/api/v1/auth/register",
                json={"username": username, "display_name": "Batch Applicant", "password": "TestPassword-2026!"},
            )
            assert response.status_code == 201, response.text
            with SessionLocal() as db:
                user = db.scalar(select(User).where(User.username == username))
                assert user is not None
                registered_uids.append(user.user_uid)

        invalid = client.post(
            "/api/v1/users/batch-approve",
            headers={"X-CSRF-Token": csrf},
            json={"user_uids": [registered_uids[0], uuid4().hex], "role": "reviewer"},
        )
        assert invalid.status_code == 409
        with SessionLocal() as db:
            assert db.scalar(select(User).where(User.user_uid == registered_uids[0])).is_approved is False

        approved = client.post(
            "/api/v1/users/batch-approve",
            headers={"X-CSRF-Token": csrf},
            json={"user_uids": registered_uids, "role": "reviewer"},
        )
        assert approved.status_code == 200, approved.text
        assert len(approved.json()) == 2
        assert all(row["role"] == "reviewer" and row["is_active"] and row["is_approved"] for row in approved.json())
        assert client.post(
            "/api/v1/users/batch-approve",
            headers={"X-CSRF-Token": csrf},
            json={"user_uids": registered_uids, "role": "manager"},
        ).status_code == 409
        assert client.post(
            "/api/v1/users/batch-approve",
            headers={"X-CSRF-Token": csrf},
            json={"user_uids": registered_uids, "role": "admin"},
        ).status_code == 422
    finally:
        for uid in registered_uids:
            cleanup_test_user(uid)
        cleanup_test_user(admin.user_uid)


def test_invite_registration_is_bounded_and_revocable() -> None:
    admin = create_test_user("admin")
    viewer = create_test_user("viewer")
    admin_client = TestClient(app)
    csrf = login_client(admin_client, admin.username)
    viewer_client = TestClient(app)
    login_client(viewer_client, viewer.username)
    invite_uid: str | None = None
    registered_uids: list[str] = []
    office_uid = get_snapshot().offices[0].stable_uid
    try:
        created = admin_client.post(
            "/api/v1/users/invites",
            headers={"X-CSRF-Token": csrf},
            json={"label": "审核人员集中注册", "role": "reviewer", "max_uses": 2, "valid_days": 1, "office_scope_uid": office_uid},
        )
        assert created.status_code == 201, created.text
        invite_uid = created.json()["invite_uid"]
        code = created.json()["code"]
        assert viewer_client.get("/api/v1/users/invites").status_code == 403
        listed = admin_client.get("/api/v1/users/invites")
        assert listed.status_code == 200
        assert code not in listed.text

        for index in range(2):
            username = f"invited-{uuid4().hex[:12]}"
            response = TestClient(app).post(
                "/api/v1/auth/register",
                json={"username": username, "display_name": f"Invited {index}", "password": "TestPassword-2026!", "invite_code": code},
            )
            assert response.status_code == 201, response.text
            assert response.json()["active"] is True
            with SessionLocal() as db:
                user = db.scalar(select(User).where(User.username == username))
                assert user is not None and user.role == "reviewer" and user.is_approved
                assert user.office_scope_uid == office_uid
                registered_uids.append(user.user_uid)
            login_client(TestClient(app), username)

        exhausted = TestClient(app).post(
            "/api/v1/auth/register",
            json={"username": f"invited-{uuid4().hex[:12]}", "display_name": "Extra", "password": "TestPassword-2026!", "invite_code": code},
        )
        assert exhausted.status_code == 400
        revoked = admin_client.post(f"/api/v1/users/invites/{invite_uid}/revoke", headers={"X-CSRF-Token": csrf})
        assert revoked.status_code == 200 and revoked.json()["revoked_at"]
    finally:
        for uid in registered_uids:
            cleanup_test_user(uid)
        if invite_uid:
            with SessionLocal() as db:
                row = db.scalar(select(RegistrationInvite).where(RegistrationInvite.invite_uid == invite_uid))
                if row:
                    db.delete(row)
                    db.commit()
        cleanup_test_user(viewer.user_uid)
        cleanup_test_user(admin.user_uid)
