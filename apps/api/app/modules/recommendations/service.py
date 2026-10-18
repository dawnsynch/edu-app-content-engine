import base64
import json
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.core.settings import Settings
from app.modules.content.enums import ContentType
from app.modules.recommendations.cache import RecommendationCache
from app.modules.recommendations.enums import SkillLevel
from app.modules.recommendations.models import (
    EngagementEvent,
    LearnerContentSignal,
    LearnerProfile,
)
from app.modules.recommendations.repository import (
    RecommendationCandidate,
    RecommendationRepository,
)
from app.modules.recommendations.schemas import (
    BookmarkItem,
    EngagementCreate,
    LearnerProfileCreate,
    LearnerProfileUpdate,
    RecommendationContent,
    RecommendationItem,
    RecommendationResponse,
    ScoreComponent,
    ScoreExplanation,
    SignalResponse,
)
from app.modules.recommendations.scoring import ScoredCandidate, diversify, score_candidate


class RecommendationService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        cache: RecommendationCache | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.cache = cache
        self.repository = RecommendationRepository(session)

    async def create_profile(self, data: LearnerProfileCreate) -> LearnerProfile:
        profile = LearnerProfile(**data.model_dump(mode="json"))
        await self.repository.create_profile(profile)
        await self.session.commit()
        await self.session.refresh(profile)
        return profile

    async def get_profile(self, learner_id: UUID) -> LearnerProfile:
        profile = await self.repository.get_profile(learner_id)
        if profile is None:
            raise ResourceNotFoundError("learner profile not found")
        return profile

    async def update_profile(
        self, learner_id: UUID, data: LearnerProfileUpdate
    ) -> LearnerProfile:
        profile = await self.get_profile(learner_id)
        for field, value in data.model_dump(exclude_unset=True, mode="json").items():
            setattr(profile, field, value)
        profile.recommendation_version += 1
        await self.session.commit()
        await self.session.refresh(profile)
        return profile

    async def set_signal(
        self, learner_id: UUID, content_id: int, *, signal_name: str, enabled: bool
    ) -> SignalResponse:
        profile = await self.get_profile(learner_id)
        if not await self.repository.content_exists(content_id):
            raise ResourceNotFoundError("content item not found")
        signal = await self.repository.get_signal(learner_id, content_id)
        if signal is None:
            signal = LearnerContentSignal(learner_id=learner_id, content_id=content_id)
            self.session.add(signal)
        setattr(signal, signal_name, enabled)
        if enabled and signal_name == "bookmarked":
            signal.dismissed = False
        if enabled and signal_name == "dismissed":
            signal.bookmarked = False
        profile.recommendation_version += 1
        if not signal.bookmarked and not signal.dismissed:
            await self.session.flush()
            await self.repository.delete_signal(signal)
        await self.session.commit()
        return SignalResponse(
            learner_id=learner_id,
            content_id=content_id,
            bookmarked=signal.bookmarked,
            dismissed=signal.dismissed,
        )

    async def record_engagement(
        self, learner_id: UUID, data: EngagementCreate
    ) -> EngagementEvent:
        profile = await self.get_profile(learner_id)
        if not await self.repository.content_exists(data.content_id):
            raise ResourceNotFoundError("content item not found")
        event = EngagementEvent(
            learner_id=learner_id,
            **data.model_dump(mode="json"),
        )
        await self.repository.add_event(event)
        profile.recommendation_version += 1
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def bookmarks(
        self, learner_id: UUID, *, after_id: int | None, limit: int
    ) -> tuple[list[BookmarkItem], int | None]:
        await self.get_profile(learner_id)
        rows = await self.repository.list_bookmarks(
            learner_id, after_id=after_id, limit=limit
        )
        has_more = len(rows) > limit
        selected = rows[:limit]
        items = [
            BookmarkItem(
                signal_id=signal.id,
                content=RecommendationContent(
                    id=content.id,
                    source_id=content.source_id,
                    source_name=source.name,
                    attribution=(
                        source.attribution_text if source.attribution_required else None
                    ),
                    canonical_url=content.canonical_url,
                    title=content.title,
                    description=content.description if source.allow_summaries else None,
                    content_type=ContentType(content.content_type),
                    author_name=content.author_name,
                    language_code=content.language_code,
                    thumbnail_url=(
                        content.thumbnail_url if source.allow_thumbnails else None
                    ),
                    duration_seconds=content.duration_seconds,
                    published_at=content.published_at,
                ),
            )
            for signal, content, source in selected
        ]
        return items, selected[-1][0].id if has_more and selected else None

    @staticmethod
    def _content(candidate: RecommendationCandidate) -> RecommendationContent:
        item = candidate.content
        return RecommendationContent(
            id=item.id,
            source_id=item.source_id,
            source_name=candidate.source_name,
            attribution=candidate.source_attribution,
            canonical_url=item.canonical_url,
            title=item.title,
            description=item.description if candidate.source_allow_summaries else None,
            content_type=ContentType(item.content_type),
            author_name=item.author_name,
            language_code=item.language_code,
            thumbnail_url=item.thumbnail_url if candidate.source_allow_thumbnails else None,
            duration_seconds=item.duration_seconds,
            published_at=item.published_at,
        )

    @classmethod
    def _item(cls, scored: ScoredCandidate) -> RecommendationItem:
        return RecommendationItem(
            content=cls._content(scored.candidate),
            score=scored.score,
            explanation=ScoreExplanation(
                components={
                    name: ScoreComponent(
                        weight=component.weight,
                        value=component.value,
                        contribution=component.contribution,
                        reason=component.reason,
                    )
                    for name, component in scored.components.items()
                },
                matched_careers=scored.matched_careers,
                matched_domains=scored.matched_domains,
                interaction_signals=scored.interaction_signals,
            ),
        )

    @staticmethod
    def _cursor(version: int, offset: int) -> str:
        raw = json.dumps({"v": version, "o": offset}, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @staticmethod
    def _offset(cursor: str | None, version: int) -> int:
        if cursor is None:
            return 0
        try:
            padding = "=" * (-len(cursor) % 4)
            value = json.loads(base64.urlsafe_b64decode(cursor + padding))
            if value["v"] != version or not isinstance(value["o"], int) or value["o"] < 0:
                raise ValueError
            return value["o"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("invalid or stale recommendation cursor") from exc

    async def _ranked(self, profile: LearnerProfile) -> tuple[list[RecommendationItem], bool]:
        cached = (
            await self.cache.get(str(profile.id), profile.recommendation_version)
            if self.cache
            else None
        )
        if cached:
            try:
                payload = json.loads(cached)
                cached_items = [
                    RecommendationItem.model_validate(item) for item in payload["items"]
                ]
                current_candidates = await self.repository.candidates(
                    limit=self.settings.recommendation_candidate_limit
                )
                current_by_id = {
                    candidate.content.id: candidate for candidate in current_candidates
                }
                current_items = [
                    item.model_copy(
                        update={
                            "content": self._content(current_by_id[item.content.id])
                        }
                    )
                    for item in cached_items
                    if item.content.id in current_by_id
                ]
                return current_items, bool(payload["diversity_applied"])
            except (KeyError, TypeError, json.JSONDecodeError, ValidationError):
                pass

        interactions = await self.repository.interactions(profile.id)
        candidates = await self.repository.candidates(
            limit=self.settings.recommendation_candidate_limit
        )
        ranked = [
            score_candidate(
                candidate,
                career_preferences=profile.career_preferences,
                technology_domains=profile.technology_domains,
                skill_level=SkillLevel(profile.skill_level),
                interaction=interactions.get(candidate.content.id),
                now=datetime.now(UTC),
            )
            for candidate in candidates
            if not interactions.get(candidate.content.id)
            or not interactions[candidate.content.id].dismissed
        ]
        ranked.sort(key=lambda item: (-item.score, -item.candidate.content.id))
        ranked, diversity_applied = diversify(ranked, target_size=min(len(ranked), 100))
        items = [self._item(item) for item in ranked]
        if self.cache:
            await self.cache.set(
                str(profile.id),
                profile.recommendation_version,
                json.dumps(
                    {
                        "items": [item.model_dump(mode="json") for item in items],
                        "diversity_applied": diversity_applied,
                    },
                    separators=(",", ":"),
                ),
            )
        return items, diversity_applied

    async def recommendations(
        self, learner_id: UUID, *, cursor: str | None, limit: int
    ) -> RecommendationResponse:
        profile = await self.get_profile(learner_id)
        offset = self._offset(cursor, profile.recommendation_version)
        ranked, diversity_applied = await self._ranked(profile)
        items = ranked[offset : offset + limit]
        next_offset = offset + len(items)
        return RecommendationResponse(
            learner_id=profile.id,
            recommendation_version=profile.recommendation_version,
            cold_start=not profile.career_preferences and not profile.technology_domains,
            diversity_applied=diversity_applied,
            items=items,
            next_cursor=(
                self._cursor(profile.recommendation_version, next_offset)
                if next_offset < len(ranked)
                else None
            ),
        )
