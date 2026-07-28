from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "helixqa",
    broker=settings.sync_celery_broker,
    backend=settings.sync_celery_backend,
    include=["app.tasks.pipeline"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_time_limit=60 * 15,
    worker_prefetch_multiplier=1,
)
