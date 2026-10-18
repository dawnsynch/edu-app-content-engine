from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings, get_settings
from app.db.session import get_db_session
from app.modules.search.schemas import SearchContent, SearchMode, SearchResponse, SearchResult
from app.modules.search.service import SearchService

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search_content(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    q: Annotated[str, Query(min_length=2, max_length=300)],
    mode: SearchMode = SearchMode.HYBRID,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SearchResponse:
    async with httpx.AsyncClient() as client:
        rows, semantic_available = await SearchService(session, client, settings).search(
            q, mode=mode, limit=limit
        )
    return SearchResponse(
        query=q,
        mode=mode,
        semantic_available=semantic_available,
        items=[
            SearchResult(
                content=SearchContent.model_validate(item),
                score=score,
                matched_by=matched_by,
            )
            for item, score, matched_by in rows
        ],
    )
