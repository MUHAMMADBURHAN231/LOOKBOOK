import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.api.deps import DB, CurrentUser, websocket_user
from app.core.config import get_settings
from app.core.rate_limit import check_rate_limit
from app.core.redis import async_redis, task_channel
from app.core.spend import ensure_capacity
from app.db.models import Garment, TryOnTask, UserPhoto
from app.db.session import get_db
from app.services import interpreter
from app.services.gemini import GeminiError
from app.services.storage import get_storage

router = APIRouter(tags=["try-on"])
log = logging.getLogger(__name__)
HEARTBEAT_SECONDS = 20


class ExecuteIn(BaseModel):
    user_photo_id: uuid.UUID
    garment_id: uuid.UUID | None = None
    prompt: str | None = Field(default=None, min_length=3, max_length=1000)
    category: Literal["upper_body", "lower_body", "dresses"] | None = None
    enhance_face: bool = True
    pipeline: Literal["auto", "edit", "vton"] = "auto"

    @model_validator(mode="after")
    def _garment_or_prompt(self):
        if not self.garment_id and not self.prompt:
            raise ValueError("Choose a garment or describe an outfit.")
        return self


class TaskOut(BaseModel):
    task_id: uuid.UUID
    status: str
    stage: str
    progress: int
    result_url: str | None = None
    error: str | None = None
    garment_id: uuid.UUID | None = None
    prompt: str | None = None
    outfit_spec: dict | None = None
    adapter: str | None = None
    execution_time_ms: int | None = None
    created_at: datetime


def task_out(t: TryOnTask) -> TaskOut:
    return TaskOut(
        task_id=t.id,
        status=t.status,
        stage=t.stage,
        progress=t.progress_percentage,
        result_url=get_storage().presign_download(t.result_storage_key) if t.result_storage_key else None,
        error=t.error_message,
        garment_id=t.garment_id,
        prompt=t.custom_prompt,
        outfit_spec=t.outfit_spec,
        adapter=t.adapter,
        execution_time_ms=t.execution_time_ms,
        created_at=t.created_at,
    )


@router.post("/try-on/execute", response_model=TaskOut, status_code=status.HTTP_202_ACCEPTED)
async def execute(body: ExecuteIn, user: CurrentUser, db: DB):
    s = get_settings()
    await check_rate_limit(
        f"tryon:{user.id}", s.rate_tryon_per_minute, 60,
        "You're generating quickly. Please wait a few seconds before the next try-on.",
    )
    if not user.biometric_consent_granted:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Please give consent before generating try-ons.")
    photo = await db.scalar(
        select(UserPhoto).where(
            UserPhoto.id == body.user_photo_id, UserPhoto.user_id == user.id, UserPhoto.status == "ready"
        )
    )
    if not photo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found. Upload it again.")

    garment = None
    spec = None
    category = body.category
    if body.garment_id:
        garment = await db.get(Garment, body.garment_id)
        if not garment:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Garment not found.")
        category = category or (garment.category if garment.category in ("upper_body", "lower_body", "dresses") else "upper_body")
    else:
        try:
            spec = await asyncio.to_thread(interpreter.interpret, body.prompt)
        except GeminiError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Outfit interpreter unavailable: {exc}") from exc
        if not category:
            regions = {g.category for g in spec.garments}
            category = "dresses" if "dresses" in regions else ("upper_body" if "upper_body" in regions or not regions else "lower_body")

    await ensure_capacity(str(user.id))
    task = TryOnTask(
        user_id=user.id,
        user_photo_id=photo.id,
        garment_id=garment.id if garment else None,
        custom_prompt=body.prompt,
        category=category,
        enhance_face=body.enhance_face,
        pipeline=body.pipeline,
        outfit_spec=spec.model_dump() if spec else None,
    )
    db.add(task)
    await db.commit()

    from app.workers.tasks import execute_virtual_tryon

    # Off the event loop: broker I/O (and eager execution in tests) must not block other requests.
    await asyncio.to_thread(execute_virtual_tryon.delay, str(task.id))
    await db.refresh(task)
    return task_out(task)


@router.get("/try-on/tasks/{task_id}", response_model=TaskOut)
async def get_task(task_id: uuid.UUID, user: CurrentUser, db: DB):
    task = await db.scalar(select(TryOnTask).where(TryOnTask.id == task_id, TryOnTask.user_id == user.id))
    if not task:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found.")
    return task_out(task)


@router.get("/try-on/tasks", response_model=list[TaskOut])
async def list_tasks(user: CurrentUser, db: DB, limit: int = 30):
    rows = await db.scalars(
        select(TryOnTask)
        .where(TryOnTask.user_id == user.id)
        .order_by(TryOnTask.created_at.desc())
        .limit(min(max(limit, 1), 100))
    )
    return [task_out(t) for t in rows]


@router.websocket("/ws/tasks/{task_id}")
async def task_socket(websocket: WebSocket, task_id: uuid.UUID):
    """Streams stage/progress events for one task. Sends the current snapshot first, so a client
    that connects late (or reconnects) never misses the terminal state."""
    async for db in get_db():
        user = await websocket_user(websocket, db)
        task = (
            await db.scalar(select(TryOnTask).where(TryOnTask.id == task_id, TryOnTask.user_id == user.id))
            if user
            else None
        )
        break
    if not task:
        await websocket.close(code=4403)
        return

    await websocket.accept()
    pubsub = async_redis().pubsub()
    # Subscribe *before* reading the snapshot, so an event published in between isn't lost.
    await pubsub.subscribe(task_channel(str(task_id)))
    try:
        async for db in get_db():
            task = await db.get(TryOnTask, task_id)
            break
        snapshot = task_out(task).model_dump(mode="json")
        await websocket.send_json({"type": "snapshot", **snapshot})
        if task.status in ("COMPLETED", "FAILED"):
            return

        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=HEARTBEAT_SECONDS)
            if message is None:
                await websocket.send_json({"type": "ping"})
                continue
            event = json.loads(message["data"])
            if event["stage"] in ("COMPLETED", "FAILED"):
                # Re-read so the client gets a fresh signed result URL.
                async for db in get_db():
                    fresh = await db.get(TryOnTask, task_id)
                    await websocket.send_json({"type": "snapshot", **task_out(fresh).model_dump(mode="json")})
                    break
                return
            await websocket.send_json({"type": "progress", **event})
    except (WebSocketDisconnect, RuntimeError):
        pass  # client went away
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()
        try:
            await websocket.close()
        except RuntimeError:
            pass
