from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.db.session import engine


router = APIRouter(tags=["System"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "yinda-web-center-api",
    }


@router.get("/health/database")
def database_health_check() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            database_name, database_user = connection.execute(
                text("SELECT current_database(), current_user")
            ).one()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database connection is unavailable.",
        ) from exc

    return {
        "status": "ok",
        "database": str(database_name),
        "user": str(database_user),
        "engine": "postgresql",
    }
