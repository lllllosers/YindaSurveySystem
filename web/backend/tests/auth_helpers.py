from sqlalchemy import select
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.auth import User
from app.schemas.auth import UserCreate
from app.services.auth_service import create_user, revoke_all_sessions


TEST_PASSWORD = "TestPassword-2026!"


def create_test_user(role: str) -> User:
    from uuid import uuid4

    token = uuid4().hex[:12]
    with SessionLocal() as db:
        user = create_user(
            db,
            UserCreate(
                username=f"test-{role}-{token}",
                display_name=f"Test {role}",
                password=TEST_PASSWORD,
                role=role,
                is_active=True,
            ),
        )
        db.expunge(user)
        return user


def login_client(client: TestClient, username: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": username,
            "password": TEST_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def cleanup_test_user(user_uid: str) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.user_uid == user_uid))
        if user is None:
            return
        revoke_all_sessions(db, user.id, commit=False)
        db.delete(user)
        db.commit()
