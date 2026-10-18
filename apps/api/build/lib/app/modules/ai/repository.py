from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.models import AIUsageEvent, ContentEnrichment
from app.modules.content.models import ContentItem
from app.modules.sources.models import Source


class AIRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_enrichment(self, content_id: int) -> ContentEnrichment | None:
        return cast(
            ContentEnrichment | None,
            await self.session.scalar(
                select(ContentEnrichment).where(ContentEnrichment.content_id == content_id)
            ),
        )

    async def get_context(self, content_id: int) -> tuple[ContentItem, Source] | None:
        row = (
            await self.session.execute(
                select(ContentItem, Source)
                .join(Source, Source.id == ContentItem.source_id)
                .where(ContentItem.id == content_id, Source.archived_at.is_(None))
            )
        ).one_or_none()
        return (row[0], row[1]) if row else None

    async def add_enrichment(self, enrichment: ContentEnrichment) -> ContentEnrichment:
        self.session.add(enrichment)
        await self.session.flush()
        return enrichment

    async def add_usage(self, event: AIUsageEvent) -> AIUsageEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def pending_content_ids(
        self,
        *,
        limit: int,
        model_alias: str,
        embedding_model: str,
        prompt_version: str,
        schema_version: str,
    ) -> list[int]:
        stale_configuration = and_(
            ContentEnrichment.review_decision.is_(None),
            or_(
                ContentEnrichment.model_alias != model_alias,
                ContentEnrichment.prompt_version != prompt_version,
                ContentEnrichment.schema_version != schema_version,
                and_(
                    Source.allow_embeddings.is_(True),
                    ContentEnrichment.status == "completed",
                    ContentEnrichment.embedding_model.is_distinct_from(embedding_model),
                ),
            ),
        )
        statement = (
            select(ContentItem.id)
            .join(Source, Source.id == ContentItem.source_id)
            .outerjoin(ContentEnrichment, ContentEnrichment.content_id == ContentItem.id)
            .where(
                ContentItem.status == "validated",
                Source.status == "active",
                Source.rights_status.in_(("approved", "restricted")),
                Source.archived_at.is_(None),
                or_(
                    ContentItem.retention_expires_at.is_(None),
                    ContentItem.retention_expires_at > func.now(),
                ),
                or_(
                    ContentEnrichment.id.is_(None),
                    stale_configuration,
                    and_(
                        ContentEnrichment.status.in_(("completed", "review_required", "skipped")),
                        ContentItem.updated_at > ContentEnrichment.updated_at,
                    ),
                ),
            )
            .order_by(ContentItem.id)
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).all())

    async def list_review_queue(
        self, *, after_id: int | None, limit: int
    ) -> list[ContentEnrichment]:
        statement = select(ContentEnrichment).where(ContentEnrichment.status == "review_required")
        if after_id is not None:
            statement = statement.where(ContentEnrichment.id > after_id)
        return list(
            (
                await self.session.scalars(
                    statement.order_by(ContentEnrichment.id).limit(limit + 1)
                )
            ).all()
        )

    async def list_usage(self, *, limit: int) -> list[AIUsageEvent]:
        return list(
            (
                await self.session.scalars(
                    select(AIUsageEvent)
                    .order_by(AIUsageEvent.created_at.desc(), AIUsageEvent.id.desc())
                    .limit(limit)
                )
            ).all()
        )

    async def usage_totals(self) -> tuple[int, int, int, int, Decimal, int]:
        row = (
            await self.session.execute(
                select(
                    func.count(AIUsageEvent.id),
                    func.coalesce(func.sum(AIUsageEvent.input_tokens), 0),
                    func.coalesce(func.sum(AIUsageEvent.output_tokens), 0),
                    func.coalesce(func.sum(AIUsageEvent.total_tokens), 0),
                    func.coalesce(func.sum(AIUsageEvent.cost_usd), 0),
                    func.count(AIUsageEvent.id).filter(AIUsageEvent.cost_usd.is_(None)),
                )
            )
        ).one()
        total_cost = row[4]
        return (
            int(row[0]),
            int(row[1]),
            int(row[2]),
            int(row[3]),
            Decimal(0) if total_cost is None else Decimal(total_cost),
            int(row[5]),
        )

    @staticmethod
    def searchable_statement() -> Select[Any]:
        return (
            select(ContentItem)
            .join(Source, Source.id == ContentItem.source_id)
            .join(ContentEnrichment, ContentEnrichment.content_id == ContentItem.id)
            .where(
                ContentItem.status == "validated",
                Source.status == "active",
                Source.archived_at.is_(None),
                Source.rights_status.in_(("approved", "restricted")),
                ContentEnrichment.status == "completed",
                ContentEnrichment.moderation_status == "safe",
                or_(
                    ContentItem.retention_expires_at.is_(None),
                    ContentItem.retention_expires_at > func.now(),
                ),
            )
        )

    async def keyword_search(self, query: str, *, limit: int) -> list[tuple[ContentItem, float]]:
        document = func.to_tsvector(
            "english",
            func.coalesce(ContentItem.title, "") + " " + func.coalesce(ContentItem.description, ""),
        )
        terms = func.websearch_to_tsquery("english", query)
        rank = func.ts_rank_cd(document, terms).label("rank")
        statement = (
            self.searchable_statement()
            .add_columns(rank)
            .where(document.op("@@")(terms))
            .order_by(rank.desc(), ContentItem.id.desc())
            .limit(limit)
        )
        rows = (await self.session.execute(statement)).all()
        return [(row[0], float(row[1])) for row in rows]

    async def searchable_by_ids(self, ids: list[int]) -> dict[int, ContentItem]:
        if not ids:
            return {}
        statement = self.searchable_statement().where(ContentItem.id.in_(ids))
        items = list((await self.session.scalars(statement)).all())
        return {item.id: item for item in items}

    async def expired_vector_content_ids(self, *, before: datetime, limit: int) -> list[int]:
        statement = (
            select(ContentEnrichment.content_id)
            .join(ContentItem, ContentItem.id == ContentEnrichment.content_id)
            .where(
                ContentEnrichment.vector_point_id.is_not(None),
                ContentItem.retention_expires_at.is_not(None),
                ContentItem.retention_expires_at <= before,
            )
            .order_by(ContentItem.retention_expires_at, ContentItem.id)
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).all())

    async def clear_vector_references(self, content_ids: list[int]) -> None:
        if not content_ids:
            return
        await self.session.execute(
            update(ContentEnrichment)
            .where(ContentEnrichment.content_id.in_(content_ids))
            .values(
                vector_point_id=None,
                embedding_model=None,
                embedding_dimensions=None,
            )
        )
