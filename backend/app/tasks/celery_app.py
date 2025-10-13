from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "threadsense",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.ingest"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3300,
    result_expires=86400,
    broker_connection_retry_on_startup=True,
)
