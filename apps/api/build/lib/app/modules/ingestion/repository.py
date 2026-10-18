from datetime import UTC, datetime
from typing import cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ingestion.models import IngestionRun, SourceSyncState
from app.modules.sources.models import Source


class IngestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_run(self, run: IngestionRun) -> IngestionRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run(self, run_id: int) -> IngestionRun | None:
        return cast(
            IngestionRun | None,
            await self.session.scalar(select(IngestionRun).where(IngestionRun.id == run_id)),
        )

    async def list_runs(
        self,
        *,
        after_id: int | None,
        limit: int,
        source_id: int | None,
        status: str | None,
    ) -> list[IngestionRun]:
        statement = select(IngestionRun)
        if after_id is not None:
            statement = statement.where(IngestionRun.id > after_id)
        if source_id is not None:
            statement = statement.where(IngestionRun.source_id == source_id)
        if status is not None:
            statement = statement.where(IngestionRun.status == status)
        statement = statement.order_by(IngestionRun.id).limit(limit + 1)
        return list((await self.session.scalars(statement)).all())

    async def get_state(self, source_id: int) -> SourceSyncState | None:
        return cast(
            SourceSyncState | None,
            await self.session.scalar(
                select(SourceSyncState).where(SourceSyncState.source_id == source_id)
            ),
        )

    async def get_or_create_state(self, source_id: int) -> SourceSyncState:
        state = await self.get_state(source_id)
        if state is None:
            state = SourceSyncState(source_id=source_id)
            self.session.add(state)
            await self.session.flush()
        return state

    async def due_source_ids(self, *, limit: int = 100) -> list[int]:
        now = datetime.now(UTC)
        statement = (
            select(Source.id)
            .outerjoin(SourceSyncState, SourceSyncState.source_id == Source.id)
            .where(
                Source.status == "active",
                Source.source_type.in_(("rss", "owned_cms", "youtube")),
                Source.archived_at.is_(None),
                or_(
                    SourceSyncState.source_id.is_(None),
                    SourceSyncState.next_due_at.is_(None),
                    SourceSyncState.next_due_at <= now,
                ),
            )
            .order_by(Source.id)
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).all())
