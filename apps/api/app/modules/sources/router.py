from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin
from app.db.session import get_db_session
from app.modules.sources.enums import SourceStatus
from app.modules.sources.schemas import (
    SourceCreate,
    SourceListResponse,
    SourceResponse,
    SourceUpdate,
)
from app.modules.sources.service import SourceService

router = APIRouter(
    prefix="/api/v1/admin/sources",
    tags=["admin-sources"],
    dependencies=[Depends(require_admin)],
)


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    data: SourceCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SourceResponse:
    source = await SourceService(session).create(data)
    return SourceResponse.model_validate(source)


@router.get("", response_model=SourceListResponse)
async def list_sources(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    after_id: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    source_status: Annotated[SourceStatus | None, Query(alias="status")] = None,
) -> SourceListResponse:
    items, next_cursor = await SourceService(session).list(
        after_id=after_id,
        limit=limit,
        status=source_status.value if source_status else None,
    )
    return SourceListResponse(
        items=[SourceResponse.model_validate(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SourceResponse:
    return SourceResponse.model_validate(await SourceService(session).get(source_id))


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: int,
    data: SourceUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SourceResponse:
    source = await SourceService(session).update(source_id, data)
    return SourceResponse.model_validate(source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_source(
    source_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    await SourceService(session).archive(source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
