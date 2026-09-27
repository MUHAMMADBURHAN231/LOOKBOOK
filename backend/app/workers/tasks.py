"""Background jobs: the try-on state machine and the nightly retention purge."""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import delete, select, update

from app.core.config import get_settings
from app.core.redis import sync_redis, task_channel
from app.core.spend import send_alert
from app.db.models import AuthSession, PasswordResetToken, TryOnTask, UserPhoto
from app.db.session import sync_session
from app.services.moderation import ContentRefused, screen_portrait
from app.services.outfit import OutfitSpec
from app.services.pipeline.adapters import select_adapter
from app.services.pipeline.base import PipelineError, TransientPipelineError, TryOnJob
from app.services.storage import StorageError, get_storage
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)
MAX_RETRIES = 2


def publish(task_id: str, stage: str, progress: int, payload: dict | None = None) -> None:
    """Persist the stage and broadcast it to WebSocket subscribers."""
    status = stage if stage in ("COMPLETED", "FAILED", "QUEUED") else "PROCESSING"
    values = {"stage": stage, "progress_percentage": progress, "status": status}
    if stage == "FAILED" and payload and payload.get("error"):
        values["error_message"] = payload["error"][:500]
    with sync_session() as db:
        db.execute(update(TryOnTask).where(TryOnTask.id == uuid.UUID(task_id)).values(**values))
    event = {"task_id": task_id, "stage": stage, "progress": progress, "payload": payload or {}}
    sync_redis().publish(task_channel(task_id), json.dumps(event))


def _load_job(task_id: str) -> tuple[TryOnTask, TryOnJob]:
    storage = get_storage()
    with sync_session() as db:
        task = db.scalar(select(TryOnTask).where(TryOnTask.id == uuid.UUID(task_id)))
        if task is None:
            raise PipelineError("Task no longer exists")
        photo = db.get(UserPhoto, task.user_photo_id) if task.user_photo_id else None
        if photo is None or photo.status != "ready":
            raise PipelineError("The source photo was deleted")
        garment = task.garment
        spec = OutfitSpec.model_validate(task.outfit_spec) if task.outfit_spec else None
        description = (
            garment.description if garment else (spec.summary if spec else task.custom_prompt or "")
        )
        job = TryOnJob(
            photo=storage.get(photo.storage_key),
            category=task.category,
            enhance_face=task.enhance_face,
            description=description,
            spec=spec,
            garment_image=storage.get(garment.image_key) if garment else None,
            garment_title=garment.title if garment else "",
        )
        return task, job


@celery_app.task(bind=True, max_retries=MAX_RETRIES, name="app.workers.tasks.execute_virtual_tryon")
def execute_virtual_tryon(self: Task, task_id: str) -> dict:
    started = time.perf_counter()
    try:
        publish(task_id, "PREPARING_INPUTS", 8)
        task, job = _load_job(task_id)

        publish(task_id, "SAFETY_CHECK", 12)
        asyncio.run(screen_portrait(job.photo))

        adapter = select_adapter(task.pipeline)
        with sync_session() as db:
            db.execute(update(TryOnTask).where(TryOnTask.id == task.id).values(adapter=adapter.name))

        async def report(stage: str, progress: int) -> None:
            await asyncio.to_thread(publish, task_id, stage, progress)

        result = asyncio.run(adapter.run(job, report))

        publish(task_id, "UPLOADING", 95)
        key = f"results/{task.user_id}/{task_id}.webp"
        get_storage().put(key, result.image, result.content_type)
        elapsed = int((time.perf_counter() - started) * 1000)
        with sync_session() as db:
            db.execute(
                update(TryOnTask)
                .where(TryOnTask.id == task.id)
                .values(result_storage_key=key, execution_time_ms=elapsed)
            )
            if result.extras.get("pose_keypoints") and task.user_photo_id:
                db.execute(
                    update(UserPhoto)
                    .where(UserPhoto.id == task.user_photo_id)
                    .values(pose_keypoints=result.extras["pose_keypoints"])
                )
        publish(task_id, "COMPLETED", 100, {"execution_time_ms": elapsed})
        return {"status": "SUCCESS", "task_id": task_id}

    except (TransientPipelineError, StorageError, SoftTimeLimitExceeded) as exc:
        if self.request.retries < MAX_RETRIES:
            publish(task_id, "RETRYING", 5, {"attempt": self.request.retries + 1})
            raise self.retry(exc=exc, countdown=10 * (2**self.request.retries)) from exc
        _fail(task_id, "The try-on service is busy right now. Please try again in a minute.", exc)
    except ContentRefused as exc:
        _fail(task_id, str(exc), None)
    except PipelineError as exc:
        _fail(task_id, "We couldn't generate this look. Try a different photo or description.", exc)
    except Exception as exc:  # noqa: BLE001 - last-resort guard so the task never hangs in PROCESSING
        log.exception("Unexpected try-on failure for task %s", task_id)
        _fail(task_id, "Something went wrong on our side. Please try again.", exc)
    return {"status": "FAILED", "task_id": task_id}


def _fail(task_id: str, user_message: str, exc: Exception | None) -> None:
    if exc is not None:
        log.warning("Try-on %s failed: %s: %s", task_id, type(exc).__name__, exc)
    publish(task_id, "FAILED", 0, {"error": user_message})


@celery_app.task(name="app.workers.tasks.purge_expired_data")
def purge_expired_data() -> dict:
    """Retention policy: raw portraits after RAW_UPLOAD_RETENTION_DAYS, results after
    RESULT_RETENTION_DAYS, plus expired sessions and reset tokens."""
    s = get_settings()
    storage = get_storage()
    now = datetime.now(timezone.utc)
    raw_cutoff = now - timedelta(days=s.raw_upload_retention_days)
    result_cutoff = now - timedelta(days=s.result_retention_days)
    counts = {"photos": 0, "results": 0, "sessions": 0, "reset_tokens": 0}
    with sync_session() as db:
        for photo in db.scalars(select(UserPhoto).where(UserPhoto.created_at < raw_cutoff)):
            storage.delete(photo.storage_key)
            db.delete(photo)
            counts["photos"] += 1
        for t in db.scalars(select(TryOnTask).where(TryOnTask.created_at < result_cutoff)):
            if t.result_storage_key:
                storage.delete(t.result_storage_key)
            db.delete(t)
            counts["results"] += 1
        counts["sessions"] = db.execute(
            delete(AuthSession).where(
                (AuthSession.absolute_expires_at < now) | (AuthSession.idle_expires_at < now)
            )
        ).rowcount
        counts["reset_tokens"] = db.execute(
            delete(PasswordResetToken).where(PasswordResetToken.expires_at < now)
        ).rowcount
    # Belt and braces for the local backend (S3/R2 lifecycle rules handle this server-side).
    storage.purge_older_than("raw", s.raw_upload_retention_days)
    storage.purge_older_than("tmp", 1)
    log.info("Retention purge: %s", counts)
    return counts


@celery_app.task(name="app.workers.tasks.alert")
def alert(text: str) -> None:
    send_alert(text)
