from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.middleware.audit import AuditMiddleware
from app.middleware.request_limits import RequestBodyLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

from app.api.router import api_router
from app.core.config import Settings, settings


def create_app(config: Settings = settings) -> FastAPI:
    app = FastAPI(
        title=config.app_name,
        description="引大调查数据采集系统 Web 中心 API",
        version="0.3.0",
        docs_url=None if config.app_env == "production" else "/docs",
        redoc_url=None if config.app_env == "production" else "/redoc",
        openapi_url=None if config.app_env == "production" else "/openapi.json",
    )
    app.state.settings = config

    app.add_middleware(AuditMiddleware)
    if config.app_env != "production":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:8848", "http://127.0.0.1:8848"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(RequestBodyLimitMiddleware, settings=config)
    if config.app_env == "production":
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.trusted_hosts)
        app.add_middleware(SecurityHeadersMiddleware, enable_hsts=config.enable_hsts)

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_web_frontend(full_path: str):
        """Serve a built SPA from the same origin as the API in deployments."""
        dist = (Path(__file__).resolve().parents[2] / "frontend" / "dist").resolve()
        blocked_docs = (
            full_path.rstrip("/") in {"docs", "redoc", "openapi.json"}
            or full_path.startswith(("docs/", "redoc/"))
        )
        if not dist.is_dir() or full_path.startswith("api/") or (
            config.app_env == "production" and blocked_docs
        ):
            raise HTTPException(status_code=404)
        target = (dist / full_path).resolve()
        if target.is_file() and (target == dist or dist in target.parents):
            return FileResponse(target)
        if Path(full_path).suffix or (target != dist and dist not in target.parents):
            raise HTTPException(status_code=404)
        return FileResponse(dist / "index.html")

    return app


app = create_app()
