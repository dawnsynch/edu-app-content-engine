from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin
from app.core.settings import Settings, get_settings
from app.db.session import get_db_session
from app.modules.ai.repository import AIRepository
from app.modules.ai.schemas import (
    EnrichmentListResponse,
    EnrichmentResponse,
    EnrichmentTaskResponse,
    ReviewDecisionRequest,
    UsageEventResponse,
    UsageSummaryResponse,
)
from app.modules.ai.service import AIEnrichmentService
from app.modules.content.service import ContentService
from app.worker.tasks import run_content_enrichment

router = APIRouter(
    prefix="/api/v1/admin/ai",
    tags=["admin-ai"],
    dependencies=[Depends(require_admin)],
)


@router.post(
    "/content/{content_id}/enrich",
    response_model=EnrichmentTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_enrichment(
    content_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EnrichmentTaskResponse:
    await ContentService(session).get(content_id)
    task = run_content_enrichment.delay(content_id)
    return EnrichmentTaskResponse(content_id=content_id, task_id=str(task.id))


@router.get("/content/{content_id}", response_model=EnrichmentResponse)
async def get_enrichment(
    content_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EnrichmentResponse:
    async with httpx.AsyncClient() as client:
        enrichment = await AIEnrichmentService(session, client, settings).get(content_id)
    return EnrichmentResponse.model_validate(enrichment)


@router.get("/review-queue", response_model=EnrichmentListResponse)
async def review_queue(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    after_id: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> EnrichmentListResponse:
    async with httpx.AsyncClient() as client:
        items, next_cursor = await AIEnrichmentService(session, client, settings).list_review_queue(
            after_id=after_id, limit=limit
        )
    return EnrichmentListResponse(
        items=[EnrichmentResponse.model_validate(item) for item in items],
        next_cursor=next_cursor,
    )


@router.post(
    "/review-queue/{content_id}/decision",
    response_model=EnrichmentResponse,
)
async def decide_review(
    content_id: int,
    decision: ReviewDecisionRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EnrichmentResponse:
    async with httpx.AsyncClient() as client:
        enrichment = await AIEnrichmentService(session, client, settings).review(
            content_id, decision
        )
    return EnrichmentResponse.model_validate(enrichment)


@router.get("/usage", response_model=UsageSummaryResponse)
async def usage_summary(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> UsageSummaryResponse:
    repository = AIRepository(session)
    items = await repository.list_usage(limit=limit)
    (
        request_count,
        input_tokens,
        output_tokens,
        total_tokens,
        cost,
        missing_cost,
    ) = await repository.usage_totals()
    return UsageSummaryResponse(
        items=[UsageEventResponse.model_validate(item) for item in items],
        request_count=request_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        reported_cost_usd=cost,
        events_without_reported_cost=missing_cost,
    )
