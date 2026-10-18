from datetime import datetime
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content.models import ContentItem


class ContentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, item: ContentItem) -> ContentItem:
        self.session.add(item)
        await self.session.flush()
        return item

    async def get(self, content_id: int) -> ContentItem | None:
        return cast(
            ContentItem | None,
            await self.session.scalar(select(ContentItem).where(ContentItem.id == content_id)),
        )

    async def find_duplicate(
        self,
        *,
        source_id: int,
        external_id: str | None,
        canonical_url: str,
        content_fingerprint: str | None,
    ) -> ContentItem | None:
        if external_id is not None:
            item = await self.session.scalar(
                select(ContentItem).where(
                    ContentItem.source_id == source_id,
                    ContentItem.external_id == external_id,
                )
            )
            if item is not None:
                return item
        item = await self.session.scalar(
            select(ContentItem).where(ContentItem.canonical_url == canonical_url)
        )
        if item is not None:
            return item
        if content_fingerprint is not None:
            item = await self.session.scalar(
                select(ContentItem).where(ContentItem.content_fingerprint == content_fingerprint)
            )
            if item is not None:
                return item
        return None

    async def list(
        self,
        *,
        after_id: int | None,
        limit: int,
        source_id: int | None,
        content_type: str | None = None,
    ) -> list[ContentItem]:
        statement = select(ContentItem)
        if after_id is not None:
            statement = statement.where(ContentItem.id > after_id)
        if source_id is not None:
            statement = statement.where(ContentItem.source_id == source_id)
        if content_type is not None:
            statement = statement.where(ContentItem.content_type == content_type)
        statement = statement.order_by(ContentItem.id).limit(limit + 1)
        return list((await self.session.scalars(statement)).all())

    async def delete_expired(self, *, before: datetime, limit: int) -> int:
        expired_ids = list(
            (
                await self.session.scalars(
                    select(ContentItem.id)
                    .where(
                        ContentItem.retention_expires_at.is_not(None),
                        ContentItem.retention_expires_at <= before,
                    )
                    .order_by(ContentItem.retention_expires_at, ContentItem.id)
                    .limit(limit)
                )
            ).all()
        )
        if not expired_ids:
            return 0
        await self.session.execute(delete(ContentItem).where(ContentItem.id.in_(expired_ids)))
        return len(expired_ids)
