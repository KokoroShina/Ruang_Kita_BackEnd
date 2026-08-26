from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.dependencies import DbSession

router = APIRouter(tags=["health"])


@router.get("/health", response_model=None)
async def health_check(db: DbSession) -> JSONResponse | dict[str, str]:
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "down"},
        )
    return {"status": "ok", "database": "up"}
