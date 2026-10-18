import json
import os
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.settings import Settings
from app.modules.ai.models import AIUsageEvent, ContentEnrichment
from app.modules.ai.service import AIEnrichmentService
from app.modules.content.enums import ContentType
from app.modules.content.models import ContentItem
from app.modules.content.schemas import ContentCreate
from app.modules.content.service import ContentService
from app.modules.search.schemas import SearchMode
from app.modules.search.service import SearchService
from app.modules.sources.enums import RightsStatus, SourceStatus, SourceType, StorageMode
from app.modules.sources.models import Source
from app.modules.sources.schemas import SourceCreate
from app.modules.sources.service import SourceService


def analysis_decision() -> dict[str, object]:
    return {
        "topics": ["python", "programming fundamentals"],
        "skills": ["loops"],
        "career_paths": ["software developer"],
        "difficulty": "beginner",
        "quality": {
            "score": 0.84,
            "signals": {
                "completeness": 0.8,
                "clarity": 0.9,
                "authority": 0.8,
                "freshness": 0.8,
                "educational_value": 0.9,
            },
        },
        "moderation": {
            "status": "safe",
            "categories": [],
            "rationale": "Safe learning content.",
        },
        "confidence": 0.93,
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ai_enrichment_cost_tracking_and_hybrid_search() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid4().hex
    source_id: int | None = None
    content_id: int | None = None
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(f"{request.method} {request.url.path}")
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(
                200,
                headers={"x-litellm-response-cost": "0.001"},
                json={
                    "id": "analysis-1",
                    "choices": [{"message": {"content": json.dumps(analysis_decision())}}],
                    "usage": {
                        "prompt_tokens": 80,
                        "completion_tokens": 30,
                        "total_tokens": 110,
                    },
                },
            )
        if request.url.path == "/v1/embeddings":
            return httpx.Response(
                200,
                headers={"x-litellm-response-cost": "0.0001"},
                json={
                    "id": "embedding-1",
                    "data": [{"embedding": [0.1, 0.2, 0.3]}],
                    "usage": {"prompt_tokens": 8, "total_tokens": 8},
                },
            )
        if request.method == "GET" and "/collections/" in request.url.path:
            return httpx.Response(404)
        if request.method == "PUT" and request.url.path.endswith("_content_v1"):
            return httpx.Response(200, json={"result": True})
        if request.method == "PUT" and request.url.path.endswith("/points"):
            return httpx.Response(200, json={"result": {"status": "completed"}})
        if request.method == "POST" and request.url.path.endswith("/points/query"):
            return httpx.Response(
                200,
                json={"result": {"points": [{"id": content_id, "score": 0.91}]}},
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    settings = Settings(
        litellm_base_url="https://litellm.example.test",
        litellm_model="classification-alias",
        litellm_embedding_model="embedding-alias",
        qdrant_url="https://qdrant.example.test",
        qdrant_collection_prefix=f"test_{unique}",
    )

    try:
        async with session_factory() as session:
            source = await SourceService(session).create(
                SourceCreate.model_validate(
                    {
                        "name": "AI Fixture Source",
                        "slug": f"ai-fixture-{unique}",
                        "source_type": SourceType.COURSE_PROVIDER,
                        "base_url": f"https://ai-{unique}.example.test",
                        "status": SourceStatus.ACTIVE,
                        "rights_status": RightsStatus.APPROVED,
                        "storage_mode": StorageMode.METADATA_ONLY,
                        "attribution_required": True,
                        "attribution_text": "AI Fixture Source",
                        "allow_summaries": True,
                        "allow_embeddings": True,
                    }
                )
            )
            source_id = source.id
            content = await ContentService(session).create(
                ContentCreate.model_validate(
                    {
                        "source_id": source.id,
                        "external_id": f"python-{unique}",
                        "canonical_url": (f"https://ai-{unique}.example.test/python-loops"),
                        "title": f"Python loops foundation {unique}",
                        "description": "Practical programming exercises for beginners.",
                        "content_type": ContentType.COURSE,
                    }
                )
            )
            content_id = content.id
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                service = AIEnrichmentService(session, client, settings)
                enrichment = await service.enrich(content.id)
                request_count_after_first_run = len(requests)
                replay = await service.enrich(content.id)
                keyword_rows, _ = await SearchService(session, client, settings).search(
                    "Python loops", mode=SearchMode.KEYWORD, limit=10
                )
                hybrid_rows, semantic_available = await SearchService(
                    session, client, settings
                ).search("beginner Python", mode=SearchMode.HYBRID, limit=10)

            usage_count = await session.scalar(
                select(func.count())
                .select_from(AIUsageEvent)
                .where(AIUsageEvent.content_id == content.id)
            )
            assert enrichment.status == "completed"
            assert enrichment.vector_point_id == str(content.id)
            assert replay.id == enrichment.id
            assert len(requests) == request_count_after_first_run + 2
            assert usage_count == 2
            assert keyword_rows[0][0].id == content.id
            assert hybrid_rows[0][0].id == content.id
            assert semantic_available is True

            stale_settings = settings.model_copy(
                update={"ai_prompt_version": "content-enrichment-next"}
            )
            async with httpx.AsyncClient(transport=transport) as client:
                stale_service = AIEnrichmentService(session, client, stale_settings)
                assert content.id in await stale_service.pending_content_ids()
                enrichment.review_decision = "approved"
                await session.commit()
                assert content.id not in await stale_service.pending_content_ids()
    finally:
        if source_id is not None:
            async with session_factory() as cleanup:
                enrichment_ids = select(ContentEnrichment.id).where(
                    ContentEnrichment.content_id == content_id
                )
                await cleanup.execute(
                    delete(AIUsageEvent).where(
                        (AIUsageEvent.content_id == content_id)
                        | (AIUsageEvent.enrichment_id.in_(enrichment_ids))
                    )
                )
                await cleanup.execute(
                    delete(ContentEnrichment).where(ContentEnrichment.content_id == content_id)
                )
                await cleanup.execute(delete(ContentItem).where(ContentItem.source_id == source_id))
                await cleanup.execute(delete(Source).where(Source.id == source_id))
                await cleanup.commit()
        await engine.dispose()
