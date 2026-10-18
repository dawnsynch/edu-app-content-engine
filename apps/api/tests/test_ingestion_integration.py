import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.settings import Settings
from app.modules.content.enums import ContentType
from app.modules.content.models import ContentItem
from app.modules.content.schemas import ContentCreate
from app.modules.content.service import ContentService
from app.modules.ingestion.connectors.errors import TransientConnectorError
from app.modules.ingestion.enums import IngestionTrigger
from app.modules.ingestion.models import IngestionRun, SourceSyncState
from app.modules.ingestion.service import IngestionService
from app.modules.sources.enums import RightsStatus, SourceStatus, SourceType, StorageMode
from app.modules.sources.models import Source
from app.modules.sources.schemas import SourceCreate
from app.modules.sources.service import SourceService

FIXTURES = Path(__file__).parent / "fixtures" / "providers"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_incremental_ingestion_and_failure_recovery() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    source_id: int | None = None
    slug = f"fixture-feed-{uuid4().hex}"
    settings = Settings()

    try:
        async with session_factory() as session:
            source = await SourceService(session).create(
                SourceCreate.model_validate(
                    {
                        "name": "Fixture Feed",
                        "slug": slug,
                        "source_type": SourceType.RSS,
                        "base_url": f"https://feeds.example.test/{slug}.xml",
                        "allowed_domains": ["learn.example.test"],
                        "status": SourceStatus.ACTIVE,
                        "rights_status": RightsStatus.APPROVED,
                        "storage_mode": StorageMode.METADATA_ONLY,
                        "attribution_required": True,
                        "attribution_text": "Fixture Feed",
                        "retention_days": 30,
                    }
                )
            )
            source_id = source.id
            service = IngestionService(session)

            async def run_fixture(filename: str, attempt: int) -> IngestionRun:
                body = (FIXTURES / filename).read_bytes()
                transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))
                async with httpx.AsyncClient(transport=transport) as client:
                    return await service.ingest(
                        source.id,
                        trigger=IngestionTrigger.MANUAL,
                        attempt=attempt,
                        client=client,
                        settings=settings,
                    )

            initial = await run_fixture("rss_initial.xml", 1)
            replay = await run_fixture("rss_initial.xml", 1)
            incremental = await run_fixture("rss_incremental.xml", 1)

            assert initial.created_count == 2
            assert replay.discovered_count == 0
            assert incremental.created_count == 1

            state_before_failure = await service.repository.get_state(source.id)
            assert state_before_failure is not None
            checkpoint_before_failure = dict(state_before_failure.checkpoint)

            failing_transport = httpx.MockTransport(lambda request: httpx.Response(503))
            async with httpx.AsyncClient(transport=failing_transport) as client:
                with pytest.raises(TransientConnectorError):
                    await service.ingest(
                        source.id,
                        trigger=IngestionTrigger.SCHEDULED,
                        attempt=1,
                        client=client,
                        settings=settings,
                    )

            failed_state = await service.repository.get_state(source.id)
            assert failed_state is not None
            assert failed_state.checkpoint == checkpoint_before_failure
            assert failed_state.consecutive_failures == 1

            recovered = await run_fixture("rss_recovery.xml", 2)
            final_state = await service.repository.get_state(source.id)
            content_count = await session.scalar(
                select(func.count())
                .select_from(ContentItem)
                .where(ContentItem.source_id == source.id)
            )

            assert recovered.created_count == 1
            assert final_state is not None
            assert final_state.consecutive_failures == 0
            assert final_state.total_successes == 4
            assert final_state.total_failures == 1
            assert content_count == 4
    finally:
        if source_id is not None:
            async with session_factory() as cleanup:
                await cleanup.execute(delete(ContentItem).where(ContentItem.source_id == source_id))
                await cleanup.execute(
                    delete(IngestionRun).where(IngestionRun.source_id == source_id)
                )
                await cleanup.execute(
                    delete(SourceSyncState).where(SourceSyncState.source_id == source_id)
                )
                await cleanup.execute(delete(Source).where(Source.id == source_id))
                await cleanup.commit()
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_phase_two_connector_course_policy_and_retention_acceptance() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    source_ids: list[int] = []
    unique = uuid4().hex
    settings = Settings(youtube_api_key=SecretStr("fixture-key"))

    try:
        async with session_factory() as session:
            sources = SourceService(session)
            cms_source = await sources.create(
                SourceCreate.model_validate(
                    {
                        "name": "Fixture Owned CMS",
                        "slug": f"fixture-cms-{unique}",
                        "source_type": SourceType.OWNED_CMS,
                        "base_url": f"https://academy-{unique}.example.test/api/content",
                        "status": SourceStatus.ACTIVE,
                        "rights_status": RightsStatus.APPROVED,
                        "storage_mode": StorageMode.METADATA_ONLY,
                        "attribution_required": True,
                        "attribution_text": "Fixture Owned CMS",
                        "retention_days": 30,
                        "allow_summaries": True,
                    }
                )
            )
            source_ids.append(cms_source.id)
            cms_payload = json.loads((FIXTURES / "cms_page_1.json").read_text())
            cms_payload["items"][0]["canonical_url"] = (
                f"https://academy-{unique}.example.test/courses/cms-101"
            )
            cms_transport = httpx.MockTransport(
                lambda request: httpx.Response(200, json=cms_payload)
            )
            async with httpx.AsyncClient(transport=cms_transport) as client:
                cms_run = await IngestionService(session).ingest(
                    cms_source.id,
                    trigger=IngestionTrigger.MANUAL,
                    attempt=1,
                    client=client,
                    settings=settings,
                )

            assert cms_run.created_count == 1
            assert cms_run.checkpoint_after == {"cursor": "page-2"}

            channel_id = f"channel-{unique}"
            youtube_source = await sources.create(
                SourceCreate.model_validate(
                    {
                        "name": "Fixture YouTube",
                        "slug": f"fixture-youtube-{unique}",
                        "source_type": SourceType.YOUTUBE,
                        "base_url": f"https://www.youtube.com/channel/{channel_id}",
                        "status": SourceStatus.ACTIVE,
                        "rights_status": RightsStatus.RESTRICTED,
                        "storage_mode": StorageMode.METADATA_ONLY,
                        "attribution_required": True,
                        "attribution_text": "Fixture YouTube",
                        "retention_days": 30,
                        "allow_summaries": False,
                        "allow_thumbnails": False,
                        "connector_config": {"channel_id": channel_id},
                    }
                )
            )
            source_ids.append(youtube_source.id)
            youtube_payload = json.loads((FIXTURES / "youtube_search.json").read_text())
            video_id = f"video-{unique}"
            youtube_payload["items"][0]["id"]["videoId"] = video_id
            youtube_transport = httpx.MockTransport(
                lambda request: httpx.Response(200, json=youtube_payload)
            )
            async with httpx.AsyncClient(transport=youtube_transport) as client:
                youtube_run = await IngestionService(session).ingest(
                    youtube_source.id,
                    trigger=IngestionTrigger.MANUAL,
                    attempt=1,
                    client=client,
                    settings=settings,
                )

            youtube_item = await session.scalar(
                select(ContentItem).where(ContentItem.source_id == youtube_source.id)
            )
            assert youtube_run.created_count == 1
            assert youtube_item is not None
            assert youtube_item.description is None
            assert youtube_item.thumbnail_url is None
            assert youtube_item.raw_metadata == {
                "provider": "youtube",
                "channel_id": channel_id,
            }

            course_source = await sources.create(
                SourceCreate.model_validate(
                    {
                        "name": "Fixture Curated Courses",
                        "slug": f"fixture-courses-{unique}",
                        "source_type": SourceType.COURSE_PROVIDER,
                        "base_url": f"https://courses-{unique}.example.test",
                        "status": SourceStatus.ACTIVE,
                        "rights_status": RightsStatus.APPROVED,
                        "storage_mode": StorageMode.METADATA_ONLY,
                        "attribution_required": True,
                        "attribution_text": "Fixture Curated Courses",
                        "retention_days": 30,
                        "allow_summaries": False,
                        "allow_thumbnails": False,
                    }
                )
            )
            source_ids.append(course_source.id)
            course = await ContentService(session).create(
                ContentCreate.model_validate(
                    {
                        "source_id": course_source.id,
                        "external_id": f"course-{unique}",
                        "canonical_url": (f"https://courses-{unique}.example.test/catalog/cloud"),
                        "title": "Curated Cloud Course",
                        "description": "This must be removed by source policy.",
                        "thumbnail_url": (
                            f"https://courses-{unique}.example.test/images/cloud.png"
                        ),
                        "content_type": ContentType.COURSE,
                        "raw_metadata": {"curation": "manual"},
                    }
                )
            )

            assert course.description is None
            assert course.thumbnail_url is None
            course.retention_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()

            deleted = await ContentService(session).purge_expired()

            assert deleted == 1
            assert await session.get(ContentItem, course.id) is None
    finally:
        if source_ids:
            async with session_factory() as cleanup:
                await cleanup.execute(
                    delete(ContentItem).where(ContentItem.source_id.in_(source_ids))
                )
                await cleanup.execute(
                    delete(IngestionRun).where(IngestionRun.source_id.in_(source_ids))
                )
                await cleanup.execute(
                    delete(SourceSyncState).where(SourceSyncState.source_id.in_(source_ids))
                )
                await cleanup.execute(delete(Source).where(Source.id.in_(source_ids)))
                await cleanup.commit()
        await engine.dispose()
