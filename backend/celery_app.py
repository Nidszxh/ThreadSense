from app.tasks import ingest  # noqa: F401  (register tasks)
from app.tasks.celery_app import celery_app as celery
