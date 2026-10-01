"""Reject oversized requests before FastAPI parses multipart form data."""

from pathlib import Path
import shutil
import tempfile

from starlette.responses import JSONResponse

from app.core.config import BACKEND_DIR, Settings


class RequestTooLarge(Exception):
    pass


class UploadStorageFull(Exception):
    pass


class RequestBodyLimitMiddleware:
    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings

    def limit_for(self, path: str) -> int:
        if path == "/api/v1/result-submissions/upload":
            return self.settings.max_result_upload_bytes
        if path.startswith("/api/v1/online-entries/") and path.endswith("/media"):
            return self.settings.max_media_upload_bytes
        if path == "/api/v1/survey-tasks/import-existing":
            return self.settings.max_task_upload_bytes
        if path == "/api/v1/survey-tasks/handover-desktop-database":
            return self.settings.max_desktop_database_upload_bytes
        return self.settings.max_api_request_bytes

    @staticmethod
    def is_upload_path(path: str) -> bool:
        return path in {
            "/api/v1/result-submissions/upload",
            "/api/v1/survey-tasks/import-existing",
            "/api/v1/survey-tasks/handover-desktop-database",
        } or (path.startswith("/api/v1/online-entries/") and path.endswith("/media"))

    def has_disk_reserve(self, incoming_bytes: int) -> bool:
        storage = BACKEND_DIR / "storage"
        locations = (storage if storage.exists() else BACKEND_DIR, Path(tempfile.gettempdir()))
        try:
            return all(
                shutil.disk_usage(location).free - incoming_bytes >= self.settings.min_free_disk_bytes
                for location in locations
            )
        except OSError:
            return False

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        limit = self.limit_for(path)
        upload_path = self.is_upload_path(path)
        lengths = [value for key, value in scope.get("headers", []) if key.lower() == b"content-length"]
        if lengths:
            try:
                declared = [int(value) for value in lengths]
            except ValueError:
                await JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)(scope, receive, send)
                return
            if any(value < 0 for value in declared) or len(set(declared)) != 1:
                await JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)(scope, receive, send)
                return
            if declared[0] > limit:
                await JSONResponse({"detail": "Request body too large."}, status_code=413)(scope, receive, send)
                return
            if upload_path and not self.has_disk_reserve(declared[0]):
                await JSONResponse({"detail": "Insufficient storage."}, status_code=507)(scope, receive, send)
                return

        received = 0
        response_started = False
        blocked_status: int | None = None
        replacement_sent = False

        async def limited_receive():
            nonlocal received, blocked_status
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    blocked_status = 413
                    raise RequestTooLarge()
                if upload_path and not self.has_disk_reserve(len(message.get("body", b""))):
                    blocked_status = 507
                    raise UploadStorageFull()
            return message

        async def tracked_send(message):
            nonlocal response_started, replacement_sent
            replacement_body = (
                b'{"detail":"Insufficient storage."}' if blocked_status == 507
                else b'{"detail":"Request body too large."}'
            )
            if message["type"] == "http.response.start":
                response_started = True
                if blocked_status is not None:
                    message = {
                        **message,
                        "status": blocked_status,
                        "headers": [
                            (key, value) for key, value in message.get("headers", [])
                            if key.lower() not in {b"content-type", b"content-length"}
                        ] + [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(replacement_body)).encode("ascii")),
                        ],
                    }
            elif message["type"] == "http.response.body" and blocked_status is not None:
                if replacement_sent:
                    return
                replacement_sent = True
                message = {**message, "body": replacement_body, "more_body": False}
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except (RequestTooLarge, UploadStorageFull):
            if response_started:
                return
            if blocked_status == 507:
                await JSONResponse({"detail": "Insufficient storage."}, status_code=507)(scope, receive, send)
            else:
                await JSONResponse({"detail": "Request body too large."}, status_code=413)(scope, receive, send)
