from celery import Celery
from app.config import settings

celery_app = Celery(
    "nuclei_cloud",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.scan_tasks",
        "app.workers.notification_tasks",
        "app.workers.template_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # One task per worker at a time for resource-intensive scans
    task_routes={
        "app.workers.scan_tasks.*": {"queue": "scans"},
        "app.workers.notification_tasks.*": {"queue": "notifications"},
        "app.workers.template_tasks.*": {"queue": "default"},
    },
    beat_schedule={
        "sync-templates-weekly": {
            "task": "app.workers.template_tasks.sync_nuclei_templates",
            "schedule": 604800.0,  # weekly
        },
    },
)
