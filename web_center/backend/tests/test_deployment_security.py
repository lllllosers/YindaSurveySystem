from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from zipfile import ZipFile

import pytest
import httpx
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app
from app.middleware.request_limits import RequestBodyLimitMiddleware
from app.services import auth_service
from app.schemas.auth import InviteCreate
from app.db.session import SessionLocal
from app.models.auth import RegistrationInvite, User
from sqlalchemy import select
from tests.auth_helpers import cleanup_test_user, create_test_user


def config(*, production: bool = False, **values) -> Settings:
    return Settings(
        _env_file=None,
        db_password="test-only-password",
        app_env="production" if production else "development",
        session_cookie_secure=production,
        allowed_hosts="testserver,accept.example,127.0.0.1" if production else "",
        **values,
    )


def test_production_config_fails_closed() -> None:
    with pytest.raises(ValidationError, match="SESSION_COOKIE_SECURE"):
        Settings(_env_file=None, db_password="good-password", app_env="production", allowed_hosts="accept.example")
    with pytest.raises(ValidationError, match="DB_PASSWORD"):
        Settings(_env_file=None, db_password="replace-with-local-password", app_env="production", session_cookie_secure=True, allowed_hosts="accept.example")
    with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
        Settings(_env_file=None, db_password="good-password", app_env="production", session_cookie_secure=True, allowed_hosts="*")
    with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
        Settings(_env_file=None, db_password="good-password", app_env="production", session_cookie_secure=True, allowed_hosts="<public-host>")
    assert config(production=True).effective_registration_mode == "invite_only"
    assert config().effective_registration_mode == "open"


def test_docs_hosts_headers_and_health() -> None:
    development = TestClient(create_app(config()))
    assert development.get("/docs").status_code == 200
    assert development.get("/openapi.json").status_code == 200
    assert development.get("/api/v1/health", headers={"Origin": "http://localhost:8848"}).headers["access-control-allow-origin"] == "http://localhost:8848"

    production = TestClient(create_app(config(production=True)))
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert production.get(path).status_code == 404
    assert production.get("/api/v1/health", headers={"host": "other.example"}).status_code == 400
    health = production.get("/api/v1/health", headers={"host": "accept.example", "Origin": "http://localhost:8848"})
    assert health.status_code == 200 and health.json() == {"status": "ok"}
    assert "access-control-allow-origin" not in health.headers
    assert health.headers["x-content-type-options"] == "nosniff"
    assert health.headers["x-frame-options"] == "DENY"
    assert health.headers["referrer-policy"] == "no-referrer"
    assert "script-src 'self'" in health.headers["content-security-policy"]
    assert health.headers["cache-control"] == "no-store"
    database = production.get("/api/v1/health/database")
    assert database.status_code == 200
    assert database.json() == {"status": "ok"}
    assert "yinda_web_center" not in database.text and "yinda_app" not in database.text
    static = production.get("/")
    assert static.status_code == 200
    assert "cache-control" not in static.headers
    assert "strict-transport-security" not in static.headers
    hsts = TestClient(create_app(config(production=True, enable_hsts=True)))
    assert hsts.get("/api/v1/health").headers["strict-transport-security"] == "max-age=31536000"


def test_declared_body_limit_by_route() -> None:
    settings = config(production=True, max_api_request_bytes=16, max_media_upload_bytes=32, max_result_upload_bytes=64,
                      max_task_upload_bytes=48, max_desktop_database_upload_bytes=96)
    client = TestClient(create_app(settings))
    for path, size in (
        ("/api/v1/projects", 17),
        ("/api/v1/result-submissions/upload", 65),
        (f"/api/v1/online-entries/{'1' * 32}/media", 33),
        ("/api/v1/survey-tasks/import-existing", 49),
        ("/api/v1/survey-tasks/handover-desktop-database", 97),
    ):
        response = client.post(path, content=b"x" * size)
        assert response.status_code == 413, (path, response.text)
        assert response.headers["x-content-type-options"] == "nosniff"


def test_chunked_body_limit_without_content_length() -> None:
    statuses: list[int] = []
    chunks = iter((b"12345678", b"901234567"))

    async def receive():
        try:
            body = next(chunks)
        except StopIteration:
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.request", "body": body, "more_body": True}

    async def send(message):
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    async def consume(scope, receive, send):
        while True:
            message = await receive()
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = RequestBodyLimitMiddleware(consume, config(max_api_request_bytes=16))
    scope = {"type": "http", "path": "/api/v1/projects", "method": "POST", "headers": []}
    asyncio.run(middleware(scope, receive, send))
    assert statuses == [413]


def test_chunked_multipart_is_rejected_before_route_parsing() -> None:
    settings = config(max_api_request_bytes=16, max_media_upload_bytes=32, max_result_upload_bytes=64)

    async def chunks():
        yield b"--abc\r\nContent-Disposition: form-data; name=\"file\"; filename=\"x.ydresult\"\r\n"
        yield b"Content-Type: application/octet-stream\r\n\r\n" + b"x" * 64

    async def request() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(settings)), base_url="http://testserver"
        ) as client:
            return await client.post(
                "/api/v1/result-submissions/upload",
                headers={"content-type": "multipart/form-data; boundary=abc"},
                content=chunks(),
            )

    response = asyncio.run(request())
    assert response.status_code == 413, response.text


def test_disk_reserve_rejects_oversized_upload(monkeypatch, tmp_path: Path) -> None:
    from app.services import disk_space
    from app.middleware import request_limits

    monkeypatch.setattr(disk_space, "settings", SimpleNamespace(min_free_disk_bytes=80))
    monkeypatch.setattr(disk_space.shutil, "disk_usage", lambda path: SimpleNamespace(free=100))
    disk_space.require_free_space(tmp_path, 20)
    with pytest.raises(disk_space.InsufficientStorageError):
        disk_space.require_free_space(tmp_path, 21)
    monkeypatch.setattr(request_limits.shutil, "disk_usage", lambda path: SimpleNamespace(free=100))
    limited = TestClient(create_app(config(production=True, min_free_disk_bytes=80)))
    response = limited.post("/api/v1/result-submissions/upload", content=b"x" * 21)
    assert response.status_code == 507


def test_registration_modes(monkeypatch) -> None:
    from app.api.routes import auth as auth_routes

    username = f"security-{uuid4().hex[:12]}"
    created_uid = None
    admin = create_test_user("admin")
    invite_uid = None
    client = TestClient(create_app(config()))
    payload = {"username": username, "display_name": "Security Test", "password": "TestPassword-2026!"}
    try:
        monkeypatch.setattr(auth_routes, "settings", config(registration_mode="closed"))
        assert client.post("/api/v1/auth/register", json=payload).status_code == 403

        monkeypatch.setattr(auth_routes, "settings", config(registration_mode="invite_only"))
        assert client.post("/api/v1/auth/register", json=payload).status_code == 403
        assert client.post("/api/v1/auth/register", json={**payload, "invite_code": "invalid"}).status_code == 400

        with SessionLocal() as db:
            invite, code = auth_service.create_invite(
                db, InviteCreate(label="Security Test", role="viewer", max_uses=1, valid_days=1), admin
            )
            invite_uid = invite.invite_uid
        response = client.post("/api/v1/auth/register", json={**payload, "invite_code": code})
        assert response.status_code == 201 and response.json()["active"] is True
        with SessionLocal() as db:
            created_uid = db.scalar(select(User.user_uid).where(User.username == username))

        monkeypatch.setattr(auth_routes, "settings", config(registration_mode="open"))
        open_username = f"security-{uuid4().hex[:12]}"
        open_response = client.post("/api/v1/auth/register", json={**payload, "username": open_username})
        assert open_response.status_code == 201 and open_response.json()["active"] is False
        with SessionLocal() as db:
            open_uid = db.scalar(select(User.user_uid).where(User.username == open_username))
        if open_uid:
            cleanup_test_user(open_uid)
    finally:
        if created_uid:
            cleanup_test_user(created_uid)
        if invite_uid:
            with SessionLocal() as db:
                invite = db.scalar(select(RegistrationInvite).where(RegistrationInvite.invite_uid == invite_uid))
                if invite:
                    db.delete(invite)
                    db.commit()
        cleanup_test_user(admin.user_uid)


def test_deployment_bundle_excludes_runtime_and_secrets(monkeypatch, tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / "build_deploy_bundle.py"
    spec = importlib.util.spec_from_file_location("build_deploy_bundle", source)
    assert spec is not None and spec.loader is not None
    build_deploy_bundle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_deploy_bundle)

    monkeypatch.setattr(build_deploy_bundle, "OUTPUT_ROOT", tmp_path)
    build_deploy_bundle.main()
    with ZipFile(tmp_path / "yinda-web-center.zip") as archive:
        names = archive.namelist()
    required = {
        "web_center/backend/.env.example",
        "web_center/backend/alembic.ini",
        "web_center/backend/requirements.txt",
        "web_center/frontend/dist/index.html",
        "DEPLOY.md",
        "shared/protocol/constants.py",
        "src/forms/engineering/registry.py",
    }
    assert required.issubset(names)
    assert not any(
        part in {".env", "storage", "backups", "node_modules", ".venv", ".git", "tests"}
        for name in names for part in Path(name).parts
    )
