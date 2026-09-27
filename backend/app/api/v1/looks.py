import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.db.models import Look, TryOnTask
from app.services.storage import get_storage

router = APIRouter(prefix="/looks", tags=["wardrobe"])


class SaveLookIn(BaseModel):
    task_id: uuid.UUID
    title: str = Field(default="", max_length=160)
    collection: str = Field(default="", max_length=60)


class LookOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    title: str
    collection: str
    image_url: str | None
    prompt: str | None
    garment_id: uuid.UUID | None
    created_at: datetime


def look_out(lk: Look) -> LookOut:
    t = lk.task
    return LookOut(
        id=lk.id,
        task_id=t.id,
        title=lk.title,
        collection=lk.collection,
        image_url=get_storage().presign_download(t.result_storage_key) if t.result_storage_key else None,
        prompt=t.custom_prompt,
        garment_id=t.garment_id,
        created_at=lk.created_at,
    )


@router.get("", response_model=list[LookOut])
async def list_looks(user: CurrentUser, db: DB, collection: str | None = None):
    stmt = select(Look).where(Look.user_id == user.id).order_by(Look.created_at.desc())
    if collection:
        stmt = stmt.where(Look.collection == collection)
    return [look_out(lk) for lk in await db.scalars(stmt)]


@router.post("", response_model=LookOut, status_code=201)
async def save_look(body: SaveLookIn, user: CurrentUser, db: DB):
    task = await db.scalar(select(TryOnTask).where(TryOnTask.id == body.task_id, TryOnTask.user_id == user.id))
    if not task or task.status != "COMPLETED":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finished try-on not found.")
    existing = await db.scalar(select(Look).where(Look.user_id == user.id, Look.tryon_task_id == task.id))
    if existing:
        return look_out(existing)
    default_title = (task.garment.title if task.garment else task.custom_prompt or "Saved look")[:160]
    look = Look(
        user_id=user.id,
        tryon_task_id=task.id,
        title=body.title.strip() or default_title,
        collection=body.collection.strip(),
    )
    db.add(look)
    await db.commit()
    look = await db.scalar(select(Look).where(Look.id == look.id))
    return look_out(look)


@router.delete("/{look_id}", status_code=204)
async def delete_look(look_id: uuid.UUID, user: CurrentUser, db: DB):
    look = await db.scalar(select(Look).where(Look.id == look_id, Look.user_id == user.id))
    if not look:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Look not found.")
    await db.delete(look)
    await db.commit()
