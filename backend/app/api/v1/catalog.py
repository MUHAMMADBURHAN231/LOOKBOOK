from fastapi import APIRouter, Query

from app.api.deps import DB, CurrentUser
from app.core.rate_limit import check_rate_limit
from app.services import catalog
from app.services.catalog import GarmentCard

router = APIRouter(prefix="/garments", tags=["catalog"])


@router.get("", response_model=list[GarmentCard])
async def list_garments(
    user: CurrentUser,
    db: DB,
    q: str | None = Query(default=None, max_length=300),
    category: str | None = Query(default=None, max_length=32),
):
    if q:
        await check_rate_limit(f"search:{user.id}", 60, 60)
        return await catalog.search(db, q, category=category, limit=12)
    return await catalog.list_all(db, category=category)
