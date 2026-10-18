from dataclasses import dataclass
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.models import ContentEnrichment
from app.modules.content.models import ContentItem
from app.modules.recommendations.models import (
    EngagementEvent,
    LearnerContentSignal,
    LearnerProfile,
)
from app.modules.sources.models import Source


@dataclass(frozen=True)
class RecommendationCandidate:
    content: ContentItem
    source_name: str
    source_attribution: str | None
    source_allow_summaries: bool
    source_allow_thumbnails: bool
    topics: list[str]
    skills: list[str]
    career_paths: list[str]
    difficulty: str | None
    quality_score: Decimal | None


@dataclass(frozen=True)
class InteractionSummary:
    bookmarked: bool = False
    dismissed: bool = False
    event_types: tuple[str, ...] = ()


class RecommendationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_profile(self, profile: LearnerProfile) -> LearnerProfile:
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def get_profile(self, learner_id: UUID) -> LearnerProfile | None:
        return cast(LearnerProfile | None, await self.session.get(LearnerProfile, learner_id))

    async def content_exists(self, content_id: int) -> bool:
        return bool(
            await self.session.scalar(
                select(func.count(ContentItem.id)).where(ContentItem.id == content_id)
            )
        )

    async def get_signal(
        self, learner_id: UUID, content_id: int
    ) -> LearnerContentSignal | None:
        return cast(
            LearnerContentSignal | None,
            await self.session.scalar(
                select(LearnerContentSignal).where(
                    LearnerContentSignal.learner_id == learner_id,
                    LearnerContentSignal.content_id == content_id,
                )
            ),
        )

    async def delete_signal(self, signal: LearnerContentSignal) -> None:
        await self.session.delete(signal)

    async def add_event(self, event: EngagementEvent) -> EngagementEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_bookmarks(
        self, learner_id: UUID, *, after_id: int | None, limit: int
    ) -> list[tuple[LearnerContentSignal, ContentItem, Source]]:
        statement = (
            select(LearnerContentSignal, ContentItem, Source)
            .join(ContentItem, ContentItem.id == LearnerContentSignal.content_id)
            .join(Source, Source.id == ContentItem.source_id)
            .join(ContentEnrichment, ContentEnrichment.content_id == ContentItem.id)
            .where(
                LearnerContentSignal.learner_id == learner_id,
                LearnerContentSignal.bookmarked.is_(True),
                ContentItem.status == "validated",
                Source.status == "active",
                Source.archived_at.is_(None),
                Source.rights_status.in_(("approved", "restricted")),
                ContentEnrichment.status == "completed",
                ContentEnrichment.moderation_status == "safe",
                (ContentItem.retention_expires_at.is_(None))
                | (ContentItem.retention_expires_at > func.now()),
            )
        )
        if after_id is not None:
            statement = statement.where(LearnerContentSignal.id > after_id)
        rows = (
            await self.session.execute(
                statement.order_by(LearnerContentSignal.id).limit(limit + 1)
            )
        ).all()
        return [(row[0], row[1], row[2]) for row in rows]

    async def interactions(self, learner_id: UUID) -> dict[int, InteractionSummary]:
        signals = list(
            (
                await self.session.scalars(
                    select(LearnerContentSignal).where(
                        LearnerContentSignal.learner_id == learner_id
                    )
                )
            ).all()
        )
        event_rows = (
            await self.session.execute(
                select(EngagementEvent.content_id, EngagementEvent.event_type)
                .where(EngagementEvent.learner_id == learner_id)
                .distinct()
            )
        ).all()
        event_map: dict[int, list[str]] = {}
        for content_id, event_type in event_rows:
            event_map.setdefault(content_id, []).append(event_type)
        content_ids = set(event_map) | {signal.content_id for signal in signals}
        signal_map = {signal.content_id: signal for signal in signals}
        result: dict[int, InteractionSummary] = {}
        for content_id in content_ids:
            signal = signal_map.get(content_id)
            result[content_id] = InteractionSummary(
                bookmarked=signal.bookmarked if signal is not None else False,
                dismissed=signal.dismissed if signal is not None else False,
                event_types=tuple(sorted(event_map.get(content_id, []))),
            )
        return result

    async def candidates(self, *, limit: int) -> list[RecommendationCandidate]:
        statement = (
            select(ContentItem, ContentEnrichment, Source)
            .join(Source, Source.id == ContentItem.source_id)
            .join(ContentEnrichment, ContentEnrichment.content_id == ContentItem.id)
            .where(
                ContentItem.status == "validated",
                Source.status == "active",
                Source.archived_at.is_(None),
                Source.rights_status.in_(("approved", "restricted")),
                ContentEnrichment.status == "completed",
                ContentEnrichment.moderation_status == "safe",
                (ContentEnrichment.review_decision.is_(None))
                | (ContentEnrichment.review_decision == "approved"),
                (ContentItem.retention_expires_at.is_(None))
                | (ContentItem.retention_expires_at > func.now()),
            )
            .order_by(ContentItem.id.desc())
            .limit(limit)
        )
        rows = (await self.session.execute(statement)).all()
        return [
            RecommendationCandidate(
                content=row[0],
                source_name=row[2].name,
                source_attribution=(
                    row[2].attribution_text if row[2].attribution_required else None
                ),
                source_allow_summaries=row[2].allow_summaries,
                source_allow_thumbnails=row[2].allow_thumbnails,
                topics=row[1].topics,
                skills=row[1].skills,
                career_paths=row[1].career_paths,
                difficulty=row[1].difficulty,
                quality_score=row[1].quality_score,
            )
            for row in rows
        ]

    async def delete_profile_data(self, learner_id: UUID) -> None:
        await self.session.execute(
            delete(EngagementEvent).where(EngagementEvent.learner_id == learner_id)
        )
        await self.session.execute(
            delete(LearnerContentSignal).where(LearnerContentSignal.learner_id == learner_id)
        )
