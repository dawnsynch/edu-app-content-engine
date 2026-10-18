from app.worker.celery_app import celery_app


def test_retention_purge_is_scheduled_hourly() -> None:
    schedule = celery_app.conf.beat_schedule["purge-expired-content"]

    assert schedule["task"] == "retention.purge_expired_content"
    assert schedule["schedule"] == 3600.0


def test_pending_enrichment_dispatch_is_scheduled() -> None:
    schedule = celery_app.conf.beat_schedule["dispatch-pending-enrichment"]

    assert schedule["task"] == "enrichment.dispatch_pending"
    assert schedule["schedule"] == 60.0
