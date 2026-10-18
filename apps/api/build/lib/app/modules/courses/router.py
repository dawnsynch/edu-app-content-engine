from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PolicyViolationError, ResourceNotFoundError
from app.core.security import require_admin
from app.db.session import get_db_session
from app.modules.content.enums import ContentType
from app.modules.content.schemas import ContentCreate, ContentListResponse, ContentResponse
from app.modules.content.service import ContentService
from app.modules.courses.schemas import CourseCreate
from app.modules.sources.enums import SourceType
from app.modules.sources.repository import SourceRepository

router = APIRouter(
    prefix="/api/v1/admin/courses",
    tags=["admin-courses"],
    dependencies=[Depends(require_admin)],
)


@router.post("", response_model=ContentResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    data: CourseCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentResponse:
    source = await SourceRepository(session).get(data.source_id)
    if source is None:
        raise ResourceNotFoundError("source not found")
    if source.source_type != SourceType.COURSE_PROVIDER:
        raise PolicyViolationError("manual courses require a course_provider source")
    payload = ContentCreate(
        source_id=data.source_id,
        external_id=data.external_id,
        canonical_url=data.canonical_url,
        title=data.title,
        description=data.description,
        content_type=ContentType.COURSE,
        author_name=data.provider_name,
        language_code=data.language_code,
        thumbnail_url=data.thumbnail_url,
        published_at=data.published_at,
        provider_updated_at=data.published_at,
        raw_metadata={"curation": "manual", **data.metadata},
    )
    return ContentResponse.model_validate(await ContentService(session).create(payload))


@router.get("", response_model=ContentListResponse)
async def list_courses(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    after_id: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    source_id: Annotated[int | None, Query(gt=0)] = None,
) -> ContentListResponse:
    items, next_cursor = await ContentService(session).list(
        after_id=after_id,
        limit=limit,
        source_id=source_id,
        content_type=ContentType.COURSE.value,
    )
    return ContentListResponse(
        items=[ContentResponse.model_validate(item) for item in items],
        next_cursor=next_cursor,
    )
