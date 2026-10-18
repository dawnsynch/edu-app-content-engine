import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.settings import Settings
from app.modules.ai.models import ContentEnrichment
from app.modules.content.enums import ContentType
from app.modules.content.models import ContentItem
from app.modules.content.schemas import ContentCreate
from app.modules.content.service import ContentService
from app.modules.recommendations.cache import RecommendationCache
from app.modules.recommendations.models import (
    EngagementEvent,
    LearnerContentSignal,
    LearnerProfile,
)
from app.modules.recommendations.schemas import LearnerProfileCreate
from app.modules.recommendations.service import RecommendationService
from app.modules.sources.enums import RightsStatus, SourceStatus, SourceType, StorageMode
from app.modules.sources.models import Source
from app.modules.sources.schemas import SourceCreate
from app.modules.sources.service import SourceService


@pytest.mark.integration
@pytest.mark.asyncio
async def test_two_learners_receive_distinct_permission_aware_feeds() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid4().hex
    source_ids: list[int] = []
    learner_ids = []
    settings = Settings(recommendation_candidate_limit=100)

    class MemoryCache:
        def __init__(self) -> None:
            self.values: dict[tuple[str, int], str] = {}

        async def get(self, learner_id: str, version: int) -> str | None:
            return self.values.get((learner_id, version))

        async def set(self, learner_id: str, version: int, payload: str) -> None:
            self.values[(learner_id, version)] = payload

    try:
        async with session_factory() as session:
            source = await SourceService(session).create(
                SourceCreate.model_validate(
                    {
                        "name": "Recommendation Fixture",
                        "slug": f"recommendation-{unique}",
                        "source_type": SourceType.COURSE_PROVIDER,
                        "base_url": f"https://recommend-{unique}.example.test",
                        "status": SourceStatus.ACTIVE,
                        "rights_status": RightsStatus.APPROVED,
                        "storage_mode": StorageMode.METADATA_ONLY,
                        "attribution_required": True,
                        "attribution_text": "Recommendation Fixture",
                        "allow_summaries": True,
                        "allow_thumbnails": False,
                    }
                )
            )
            source_ids.append(source.id)

            async def add_content(
                slug: str,
                title: str,
                topics: list[str],
                careers: list[str],
                difficulty: str,
            ) -> ContentItem:
                content = await ContentService(session).create(
                    ContentCreate.model_validate(
                        {
                            "source_id": source.id,
                            "external_id": f"{slug}-{unique}",
                            "canonical_url": f"{source.base_url}/{slug}",
                            "title": title,
                            "description": f"Practical {title} curriculum.",
                            "content_type": ContentType.COURSE,
                            "published_at": datetime.now(UTC) - timedelta(days=5),
                        }
                    )
                )
                session.add(
                    ContentEnrichment(
                        content_id=content.id,
                        status="completed",
                        topics=topics,
                        skills=topics,
                        career_paths=careers,
                        difficulty=difficulty,
                        quality_score=Decimal("0.85"),
                        moderation_status="safe",
                        model_alias="fixture",
                        prompt_version="fixture-v1",
                        schema_version="1.0.0",
                        input_fingerprint=f"fingerprint-{slug}-{unique}",
                    )
                )
                await session.commit()
                return content

            python = await add_content(
                "python",
                "Beginner Python Development",
                ["python"],
                ["software developer"],
                "beginner",
            )
            security = await add_content(
                "security",
                "Advanced Cybersecurity Operations",
                ["cybersecurity"],
                ["security analyst"],
                "advanced",
            )
            blocked = await add_content(
                "blocked",
                "Restricted Internal Metrics",
                ["python"],
                ["software developer"],
                "beginner",
            )
            blocked.status = "rejected"
            await session.commit()

            cache = cast(RecommendationCache, MemoryCache())
            service = RecommendationService(session, settings, cache)
            beginner = await service.create_profile(
                LearnerProfileCreate(
                    career_preferences=["software developer"],
                    technology_domains=["python"],
                    skill_level="beginner",
                )
            )
            advanced = await service.create_profile(
                LearnerProfileCreate(
                    career_preferences=["security analyst"],
                    technology_domains=["cybersecurity"],
                    skill_level="advanced",
                )
            )
            learner_ids.extend((beginner.id, advanced.id))

            beginner_feed = await service.recommendations(beginner.id, cursor=None, limit=10)
            advanced_feed = await service.recommendations(advanced.id, cursor=None, limit=10)

            assert beginner_feed.items[0].content.id == python.id
            assert advanced_feed.items[0].content.id == security.id
            assert blocked.id not in {item.content.id for item in beginner_feed.items}
            assert beginner_feed.items[0].explanation.matched_domains == ["python"]
            assert advanced_feed.items[0].explanation.matched_careers == ["security analyst"]

            previous_version = beginner.recommendation_version
            await service.set_signal(
                beginner.id, python.id, signal_name="dismissed", enabled=True
            )
            refreshed = await service.recommendations(beginner.id, cursor=None, limit=10)
            assert refreshed.recommendation_version == previous_version + 1
            assert python.id not in {item.content.id for item in refreshed.items}

            source.status = SourceStatus.PAUSED
            await session.commit()
            policy_refreshed = await service.recommendations(
                beginner.id, cursor=None, limit=10
            )
            policy_ids = {item.content.id for item in policy_refreshed.items}
            assert python.id not in policy_ids
            assert security.id not in policy_ids
    finally:
        async with session_factory() as cleanup:
            if learner_ids:
                await cleanup.execute(
                    delete(EngagementEvent).where(EngagementEvent.learner_id.in_(learner_ids))
                )
                await cleanup.execute(
                    delete(LearnerContentSignal).where(
                        LearnerContentSignal.learner_id.in_(learner_ids)
                    )
                )
                await cleanup.execute(
                    delete(LearnerProfile).where(LearnerProfile.id.in_(learner_ids))
                )
            if source_ids:
                content_ids = await cleanup.scalars(
                    ContentItem.__table__.select()
                    .with_only_columns(ContentItem.id)
                    .where(ContentItem.source_id.in_(source_ids))
                )
                await cleanup.execute(
                    delete(ContentEnrichment).where(
                        ContentEnrichment.content_id.in_(list(content_ids))
                    )
                )
                await cleanup.execute(
                    delete(ContentItem).where(ContentItem.source_id.in_(source_ids))
                )
                await cleanup.execute(delete(Source).where(Source.id.in_(source_ids)))
            await cleanup.commit()
        await engine.dispose()
