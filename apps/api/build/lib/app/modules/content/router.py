from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin
from app.db.session import get_db_session
from app.modules.content.schemas import ContentCreate, ContentListResponse, ContentResponse
from app.modules.content.service import ContentService

router = APIRouter(
    prefix="/api/v1/admin/content",
    tags=["admin-content"],
    dependencies=[Depends(require_admin)],
)


@router.post("", response_model=ContentResponse, status_code=status.HTTP_201_CREATED)
async def create_content(
    data: ContentCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentResponse:
    item = await ContentService(session).create(data)
    return ContentResponse.model_validate(item)


@router.get("", response_model=ContentListResponse)
async def list_content(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    after_id: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    source_id: Annotated[int | None, Query(gt=0)] = None,
) -> ContentListResponse:
    items, next_cursor = await ContentService(session).list(
        after_id=after_id,
        limit=limit,
        source_id=source_id,
    )
    return ContentListResponse(
        items=[ContentResponse.model_validate(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/{content_id}", response_model=ContentResponse)
async def get_content(
    content_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentResponse:
    return ContentResponse.model_validate(await ContentService(session).get(content_id))
