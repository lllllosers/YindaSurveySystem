from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.audit import AuditMiddleware

from app.api.router import api_router
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    description="引大调查数据采集系统 Web 中心 API",
    version="0.3.0",
)

app.add_middleware(AuditMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8848",
        "http://127.0.0.1:8848",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/{full_path:path}", include_in_schema=False)
def serve_web_frontend(full_path: str):
    """Serve a built SPA from the same origin as the API in deployments."""
    dist = (Path(__file__).resolve().parents[2] / "frontend" / "dist").resolve()
    if not dist.is_dir() or full_path.startswith("api/"):
        raise HTTPException(status_code=404)
    target = (dist / full_path).resolve()
    if target.is_file() and (target == dist or dist in target.parents):
        return FileResponse(target)
    if Path(full_path).suffix or (target != dist and dist not in target.parents):
        raise HTTPException(status_code=404)
    return FileResponse(dist / "index.html")
