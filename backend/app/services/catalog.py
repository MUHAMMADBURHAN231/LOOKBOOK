"""Garment catalog queries (pgvector cosine similarity)."""

import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Garment
from app.services import embeddings
from app.services.storage import get_storage


class GarmentCard(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    category: str
    brand: str | None
    color: str | None
    season: str | None
    description: str
    price_cents: int | None
    image_url: str
    similarity: float | None = None


def card(g: Garment, similarity: float | None = None) -> GarmentCard:
    return GarmentCard(
        id=g.id,
        slug=g.slug,
        title=g.title,
        category=g.category,
        brand=g.brand,
        color=g.color,
        season=g.season,
        description=g.description,
        price_cents=g.price_cents,
        image_url=get_storage().presign_download(g.image_key, expires=3600),
        similarity=similarity,
    )


async def search(db: AsyncSession, query: str, category: str | None = None, limit: int = 4) -> list[GarmentCard]:
    vector = await embeddings.embed_text(query)
    distance = Garment.embedding.cosine_distance(vector)
    stmt = (
        select(Garment, (1 - distance).label("similarity"))
        .where(Garment.embedding_model == embeddings.model_name())
        .order_by(distance)
        .limit(limit)
    )
    if category:
        stmt = stmt.where(Garment.category == category)
    rows = (await db.execute(stmt)).all()
    return [card(g, round(float(sim), 4)) for g, sim in rows]


async def list_all(db: AsyncSession, category: str | None = None) -> list[GarmentCard]:
    stmt = select(Garment).order_by(Garment.category, Garment.title)
    if category:
        stmt = stmt.where(Garment.category == category)
    return [card(g) for g in await db.scalars(stmt)]
