import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx
from celery import Task
from redis import Redis

from app.core.settings import get_settings
from app.db.session import AsyncSessionLocal, engine
from app.modules.ai.errors import TransientAIError
from app.modules.ai.qdrant import QdrantVectorStore
from app.modules.ai.repository import AIRepository
from app.modules.ai.service import AIEnrichmentService
from app.modules.content.service import ContentService
from app.modules.ingestion.connectors.errors import TransientConnectorError
from app.modules.ingestion.enums import IngestionTrigger
from app.modules.ingestion.repository import IngestionRepository
from app.modules.ingestion.service import IngestionService
from app.worker.celery_app import celery_app


@celery_app.task(name="foundation.ping")  # type: ignore[misc]
def ping() -> str:
    return "pong"


async def _ingest(source_id: int, trigger: IngestionTrigger, attempt: int) -> dict[str, Any]:
    settings = get_settings()
    try:
        async with AsyncSessionLocal() as session:
            async with httpx.AsyncClient(timeout=settings.ingestion_http_timeout_seconds) as client:
                run = await IngestionService(session).ingest(
                    source_id,
                    trigger=trigger,
                    attempt=attempt,
                    client=client,
                    settings=settings,
                )
                return {
                    "run_id": run.id,
                    "source_id": source_id,
                    "status": run.status,
                    "created": run.created_count,
                    "updated": run.updated_count,
                    "unchanged": run.unchanged_count,
                    "rejected": run.rejected_count,
                }
    finally:
        await engine.dispose()


@celery_app.task(bind=True, name="ingestion.run_source", max_retries=4)  # type: ignore[misc]
def run_source_ingestion(
    self: Task,
    source_id: int,
    trigger: str = IngestionTrigger.SCHEDULED.value,
) -> dict[str, Any]:
    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url)
    lock = redis_client.lock(
        f"edu_dawnsynch:ingestion:source:{source_id}",
        timeout=settings.ingestion_lock_seconds,
        blocking_timeout=0,
    )
    if not lock.acquire(blocking=False):
        redis_client.close()
        return {"source_id": source_id, "status": "skipped", "reason": "already_running"}
    try:
        effective_trigger = (
            IngestionTrigger.RETRY if self.request.retries else IngestionTrigger(trigger)
        )
        try:
            return asyncio.run(_ingest(source_id, effective_trigger, int(self.request.retries) + 1))
        except TransientConnectorError as exc:
            countdown = min(30 * (2 ** int(self.request.retries)), 900)
            raise self.retry(
                exc=exc,
                countdown=countdown,
                max_retries=settings.ingestion_max_retries,
            ) from exc
    finally:
        try:
            lock.release()
        finally:
            redis_client.close()


async def _due_source_ids() -> list[int]:
    try:
        async with AsyncSessionLocal() as session:
            return await IngestionRepository(session).due_source_ids()
    finally:
        await engine.dispose()


@celery_app.task(name="ingestion.dispatch_due_sources")  # type: ignore[misc]
def dispatch_due_sources() -> dict[str, Any]:
    source_ids = asyncio.run(_due_source_ids())
    for source_id in source_ids:
        run_source_ingestion.delay(source_id, IngestionTrigger.SCHEDULED.value)
    return {"dispatched": len(source_ids), "source_ids": source_ids}


async def _purge_expired_content() -> int:
    settings = get_settings()
    cutoff = datetime.now(UTC)
    try:
        async with AsyncSessionLocal() as session:
            repository = AIRepository(session)
            async with httpx.AsyncClient(timeout=settings.ai_http_timeout_seconds) as client:
                vectors = QdrantVectorStore(client, settings)
                while True:
                    content_ids = await repository.expired_vector_content_ids(
                        before=cutoff, limit=500
                    )
                    if not content_ids:
                        break
                    await vectors.delete_many(content_ids)
                    await repository.clear_vector_references(content_ids)
                    await session.commit()
            return await ContentService(session).purge_expired(before=cutoff)
    finally:
        await engine.dispose()


@celery_app.task(name="retention.purge_expired_content")  # type: ignore[misc]
def purge_expired_content() -> dict[str, int]:
    return {"deleted": asyncio.run(_purge_expired_content())}


async def _enrich_content(content_id: int) -> dict[str, Any]:
    settings = get_settings()
    try:
        async with AsyncSessionLocal() as session:
            async with httpx.AsyncClient(timeout=settings.ai_http_timeout_seconds) as client:
                enrichment = await AIEnrichmentService(session, client, settings).enrich(content_id)
                return {
                    "content_id": content_id,
                    "enrichment_id": enrichment.id,
                    "status": enrichment.status,
                    "moderation_status": enrichment.moderation_status,
                    "quality_score": (
                        str(enrichment.quality_score)
                        if enrichment.quality_score is not None
                        else None
                    ),
                }
    finally:
        await engine.dispose()


@celery_app.task(bind=True, name="enrichment.run_content", max_retries=3)  # type: ignore[misc]
def run_content_enrichment(self: Task, content_id: int) -> dict[str, Any]:
    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url)
    lock = redis_client.lock(
        f"edu_dawnsynch:enrichment:content:{content_id}",
        timeout=settings.ingestion_lock_seconds,
        blocking_timeout=0,
    )
    if not lock.acquire(blocking=False):
        redis_client.close()
        return {"content_id": content_id, "status": "skipped", "reason": "already_running"}
    try:
        try:
            return asyncio.run(_enrich_content(content_id))
        except TransientAIError as exc:
            countdown = min(30 * (2 ** int(self.request.retries)), 900)
            raise self.retry(
                exc=exc,
                countdown=countdown,
                max_retries=settings.ai_max_retries,
            ) from exc
    finally:
        try:
            lock.release()
        finally:
            redis_client.close()


async def _pending_enrichment_ids() -> list[int]:
    settings = get_settings()
    try:
        async with AsyncSessionLocal() as session:
            async with httpx.AsyncClient(timeout=settings.ai_http_timeout_seconds) as client:
                return await AIEnrichmentService(session, client, settings).pending_content_ids()
    finally:
        await engine.dispose()


@celery_app.task(name="enrichment.dispatch_pending")  # type: ignore[misc]
def dispatch_pending_enrichment() -> dict[str, Any]:
    content_ids = asyncio.run(_pending_enrichment_ids())
    for content_id in content_ids:
        run_content_enrichment.delay(content_id)
    return {"dispatched": len(content_ids), "content_ids": content_ids}
