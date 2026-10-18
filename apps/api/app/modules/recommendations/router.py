from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings, get_settings
from app.db.session import get_db_session
from app.modules.recommendations.cache import RecommendationCache
from app.modules.recommendations.schemas import (
    BookmarkListResponse,
    EngagementCreate,
    EngagementResponse,
    LearnerProfileCreate,
    LearnerProfileResponse,
    LearnerProfileUpdate,
    RecommendationResponse,
    SignalResponse,
)
from app.modules.recommendations.service import RecommendationService

router = APIRouter(prefix="/api/v1/learners", tags=["recommendations"])


@router.post("", response_model=LearnerProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_learner(
    data: LearnerProfileCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LearnerProfileResponse:
    profile = await RecommendationService(session, settings).create_profile(data)
    return LearnerProfileResponse.model_validate(profile)


@router.get("/{learner_id}/preferences", response_model=LearnerProfileResponse)
async def get_preferences(
    learner_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LearnerProfileResponse:
    profile = await RecommendationService(session, settings).get_profile(learner_id)
    return LearnerProfileResponse.model_validate(profile)


@router.patch("/{learner_id}/preferences", response_model=LearnerProfileResponse)
async def update_preferences(
    learner_id: UUID,
    data: LearnerProfileUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LearnerProfileResponse:
    profile = await RecommendationService(session, settings).update_profile(learner_id, data)
    return LearnerProfileResponse.model_validate(profile)


@router.put("/{learner_id}/bookmarks/{content_id}", response_model=SignalResponse)
async def add_bookmark(
    learner_id: UUID,
    content_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SignalResponse:
    return await RecommendationService(session, settings).set_signal(
        learner_id, content_id, signal_name="bookmarked", enabled=True
    )


@router.delete("/{learner_id}/bookmarks/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_bookmark(
    learner_id: UUID,
    content_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    await RecommendationService(session, settings).set_signal(
        learner_id, content_id, signal_name="bookmarked", enabled=False
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{learner_id}/bookmarks", response_model=BookmarkListResponse)
async def list_bookmarks(
    learner_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    after_id: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> BookmarkListResponse:
    items, next_cursor = await RecommendationService(session, settings).bookmarks(
        learner_id, after_id=after_id, limit=limit
    )
    return BookmarkListResponse(items=items, next_cursor=next_cursor)


@router.put("/{learner_id}/dismissals/{content_id}", response_model=SignalResponse)
async def dismiss_content(
    learner_id: UUID,
    content_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SignalResponse:
    return await RecommendationService(session, settings).set_signal(
        learner_id, content_id, signal_name="dismissed", enabled=True
    )


@router.delete("/{learner_id}/dismissals/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def restore_content(
    learner_id: UUID,
    content_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    await RecommendationService(session, settings).set_signal(
        learner_id, content_id, signal_name="dismissed", enabled=False
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{learner_id}/engagement-events",
    response_model=EngagementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_engagement(
    learner_id: UUID,
    data: EngagementCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EngagementResponse:
    event = await RecommendationService(session, settings).record_engagement(learner_id, data)
    return EngagementResponse.model_validate(event)


@router.get("/{learner_id}/recommendations", response_model=RecommendationResponse)
async def recommendations(
    learner_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> RecommendationResponse:
    redis = Redis.from_url(settings.redis_url)
    try:
        service = RecommendationService(
            session,
            settings,
            RecommendationCache(redis, ttl_seconds=settings.recommendation_cache_ttl_seconds),
        )
        try:
            return await service.recommendations(learner_id, cursor=cursor, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await redis.aclose()
