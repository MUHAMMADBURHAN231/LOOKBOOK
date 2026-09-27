from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level, settings.json_logs)

celery_app = Celery("lookbook_workers", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,
    # A job is acknowledged only after it finishes, so a crashed worker's job is redelivered.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=240,
    task_time_limit=300,
    task_routes={"app.workers.tasks.execute_virtual_tryon": {"queue": "tryon"}},
    task_default_queue="default",
    task_always_eager=settings.celery_eager,
    task_eager_propagates=False,
    beat_schedule={
        "purge-expired-data": {
            "task": "app.workers.tasks.purge_expired_data",
            "schedule": crontab(hour=3, minute=17),
        },
    },
)
celery_app.autodiscover_tasks(["app.workers"])
