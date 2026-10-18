from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sources.models import Source


class SourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, source: Source) -> Source:
        self.session.add(source)
        await self.session.flush()
        return source

    async def get(self, source_id: int, *, include_archived: bool = False) -> Source | None:
        statement = select(Source).where(Source.id == source_id)
        if not include_archived:
            statement = statement.where(Source.archived_at.is_(None))
        return cast(Source | None, await self.session.scalar(statement))

    async def list(
        self,
        *,
        after_id: int | None,
        limit: int,
        status: str | None,
    ) -> list[Source]:
        statement = select(Source).where(Source.archived_at.is_(None))
        if after_id is not None:
            statement = statement.where(Source.id > after_id)
        if status is not None:
            statement = statement.where(Source.status == status)
        statement = statement.order_by(Source.id).limit(limit + 1)
        return list((await self.session.scalars(statement)).all())
