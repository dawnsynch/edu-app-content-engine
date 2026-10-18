from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DuplicateResourceError,
    PolicyViolationError,
    ResourceNotFoundError,
)
from app.modules.content.models import ContentItem
from app.modules.content.repository import ContentRepository
from app.modules.content.schemas import ContentCreate
from app.modules.content.validators import normalize_http_url, validate_source_host
from app.modules.sources.enums import RightsStatus, SourceStatus
from app.modules.sources.models import Source
from app.modules.sources.repository import SourceRepository


class ContentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ContentRepository(session)
        self.sources = SourceRepository(session)

    async def _validate_source(self, source_id: int) -> Source:
        source = await self.sources.get(source_id)
        if source is None:
            raise ResourceNotFoundError("source not found")
        if source.status != SourceStatus.ACTIVE:
            raise PolicyViolationError("content requires an active source")
        if source.rights_status not in {RightsStatus.APPROVED, RightsStatus.RESTRICTED}:
            raise PolicyViolationError("content source rights are not approved")
        return source

    async def create(self, data: ContentCreate) -> ContentItem:
        source = await self._validate_source(data.source_id)

        canonical_url = normalize_http_url(str(data.canonical_url))
        validate_source_host(canonical_url, source.base_url, source.allowed_domains)
        retention_expires_at = (
            datetime.now(UTC) + timedelta(days=source.retention_days)
            if source.retention_days is not None
            else None
        )

        payload = data.model_dump(mode="python", exclude={"canonical_url", "thumbnail_url"})
        payload["canonical_url"] = canonical_url
        payload["thumbnail_url"] = (
            normalize_http_url(str(data.thumbnail_url))
            if data.thumbnail_url and source.allow_thumbnails
            else None
        )
        if not source.allow_summaries and not source.allow_snippets:
            payload["description"] = None
        payload["retention_expires_at"] = retention_expires_at
        payload["status"] = "validated"
        item = ContentItem(**payload)

        try:
            await self.repository.add(item)
            await self.session.commit()
            await self.session.refresh(item)
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateResourceError(
                "content canonical URL, source external ID, or fingerprint already exists"
            ) from exc
        return item

    async def upsert_ingested(
        self, data: ContentCreate
    ) -> tuple[ContentItem, Literal["created", "updated", "unchanged"]]:
        source = await self._validate_source(data.source_id)
        canonical_url = normalize_http_url(str(data.canonical_url))
        validate_source_host(canonical_url, source.base_url, source.allowed_domains)
        existing = await self.repository.find_duplicate(
            source_id=data.source_id,
            external_id=data.external_id,
            canonical_url=canonical_url,
            content_fingerprint=data.content_fingerprint,
        )
        if existing is None:
            return await self.create(data), "created"
        if existing.source_id != data.source_id:
            return existing, "unchanged"

        values = data.model_dump(
            mode="python",
            exclude={"source_id", "canonical_url", "thumbnail_url"},
        )
        values["canonical_url"] = canonical_url
        values["thumbnail_url"] = (
            normalize_http_url(str(data.thumbnail_url))
            if data.thumbnail_url and source.allow_thumbnails
            else None
        )
        if not source.allow_summaries and not source.allow_snippets:
            values["description"] = None
        changed = any(getattr(existing, field) != value for field, value in values.items())
        if not changed:
            return existing, "unchanged"
        for field, value in values.items():
            setattr(existing, field, value)
        if source.retention_days is not None:
            existing.retention_expires_at = datetime.now(UTC) + timedelta(
                days=source.retention_days
            )
        await self.session.commit()
        await self.session.refresh(existing)
        return existing, "updated"

    async def purge_expired(
        self,
        *,
        before: datetime | None = None,
        batch_size: int = 500,
    ) -> int:
        cutoff = before or datetime.now(UTC)
        deleted = 0
        while True:
            batch_count = await self.repository.delete_expired(
                before=cutoff,
                limit=batch_size,
            )
            if batch_count == 0:
                break
            await self.session.commit()
            deleted += batch_count
            if batch_count < batch_size:
                break
        return deleted

    async def get(self, content_id: int) -> ContentItem:
        item = await self.repository.get(content_id)
        if item is None:
            raise ResourceNotFoundError("content item not found")
        return item

    async def list(
        self,
        *,
        after_id: int | None,
        limit: int,
        source_id: int | None,
        content_type: str | None = None,
    ) -> tuple[list[ContentItem], int | None]:
        rows = await self.repository.list(
            after_id=after_id,
            limit=limit,
            source_id=source_id,
            content_type=content_type,
        )
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = items[-1].id if has_more and items else None
        return items, next_cursor
