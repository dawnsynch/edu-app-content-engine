from celery import Celery

from app.core.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "edu_dawnsynch",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.worker.tasks"],
)

celery_app.conf.timezone = "UTC"
celery_app.conf.task_track_started = True
celery_app.conf.beat_schedule = {
    "dispatch-due-ingestion-sources": {
        "task": "ingestion.dispatch_due_sources",
        "schedule": 60.0,
    },
    "purge-expired-content": {
        "task": "retention.purge_expired_content",
        "schedule": 3600.0,
    },
    "dispatch-pending-enrichment": {
        "task": "enrichment.dispatch_pending",
        "schedule": 60.0,
    },
}
