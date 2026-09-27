import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.redis import async_redis
from app.db.session import async_engine
from app.services import embeddings
from app.services.pipeline.adapters import select_adapter
from app.services.storage import get_storage

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz():
    """Readiness: dependencies reachable. Load balancers route traffic only when this is 200."""
    checks: dict[str, str] = {}
    try:
        async with async_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {type(exc).__name__}"
    try:
        await async_redis().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {type(exc).__name__}"
    try:
        await asyncio.to_thread(get_storage().ping)
        checks["storage"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["storage"] = f"error: {type(exc).__name__}"
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse({"status": "ok" if ok else "degraded", "checks": checks}, status_code=200 if ok else 503)


@router.get("/api/v1/meta")
async def meta() -> dict:
    """Public capability flags the frontend uses to adapt the UI (never secrets)."""
    s = get_settings()
    return {
        "mock": s.use_mock,
        "tryon_adapter": select_adapter("auto").name,
        "edit_available": bool(s.gemini_api_key) and not s.use_mock,
        "live_available": bool(s.decart_api_key),
        "embedding_model": embeddings.model_name(),
        "raw_upload_retention_days": s.raw_upload_retention_days,
        "max_upload_bytes": s.max_upload_bytes,
    }
