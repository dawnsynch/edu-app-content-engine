from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateResourceError, ResourceNotFoundError
from app.modules.content.validators import normalize_http_url
from app.modules.sources.models import Source
from app.modules.sources.repository import SourceRepository
from app.modules.sources.schemas import SourceCreate, SourceUpdate

SOURCE_POLICY_FIELDS = (
    "name",
    "slug",
    "source_type",
    "base_url",
    "allowed_domains",
    "status",
    "rights_status",
    "storage_mode",
    "terms_url",
    "license_name",
    "attribution_required",
    "attribution_text",
    "retention_days",
    "fetch_interval_minutes",
    "respect_robots_txt",
    "allow_summaries",
    "allow_embeddings",
    "allow_snippets",
    "allow_thumbnails",
    "policy_metadata",
    "connector_config",
    "rights_reviewed_at",
    "rights_review_due_at",
)


class SourceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SourceRepository(session)

    @staticmethod
    def _payload(data: SourceCreate) -> dict[str, object]:
        payload = data.model_dump(mode="python")
        payload["base_url"] = normalize_http_url(str(data.base_url))
        payload["terms_url"] = (
            normalize_http_url(str(data.terms_url)) if data.terms_url is not None else None
        )
        return payload

    async def create(self, data: SourceCreate) -> Source:
        source = Source(**self._payload(data))
        try:
            await self.repository.add(source)
            await self.session.commit()
            await self.session.refresh(source)
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateResourceError("source slug or base URL already exists") from exc
        return source

    async def get(self, source_id: int) -> Source:
        source = await self.repository.get(source_id)
        if source is None:
            raise ResourceNotFoundError("source not found")
        return source

    async def list(
        self, *, after_id: int | None, limit: int, status: str | None
    ) -> tuple[list[Source], int | None]:
        rows = await self.repository.list(after_id=after_id, limit=limit, status=status)
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = items[-1].id if has_more and items else None
        return items, next_cursor

    async def update(self, source_id: int, patch: SourceUpdate) -> Source:
        source = await self.get(source_id)
        merged = {field: getattr(source, field) for field in SOURCE_POLICY_FIELDS}
        merged.update(patch.model_dump(exclude_unset=True, mode="python"))
        validated = SourceCreate.model_validate(merged)

        for field, value in self._payload(validated).items():
            setattr(source, field, value)

        try:
            await self.session.commit()
            await self.session.refresh(source)
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateResourceError("source slug or base URL already exists") from exc
        return source

    async def archive(self, source_id: int) -> None:
        source = await self.get(source_id)
        source.status = "paused"
        source.archived_at = datetime.now(UTC)
        await self.session.commit()
