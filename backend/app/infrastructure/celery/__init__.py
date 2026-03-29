from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "cv_review",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.infrastructure.celery.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    # ── Crash recovery: only ack after task finishes ──
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
