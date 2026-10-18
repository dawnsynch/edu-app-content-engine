from collections.abc import Sequence
from time import monotonic

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.modules.ai.client import LiteLLMClient
from app.modules.ai.errors import AIServiceError
from app.modules.ai.models import AIUsageEvent
from app.modules.ai.qdrant import QdrantVectorStore
from app.modules.ai.repository import AIRepository
from app.modules.content.models import ContentItem
from app.modules.search.schemas import SearchMode


def reciprocal_rank_fusion(
    rankings: Sequence[tuple[str, Sequence[int], float]], *, k: int = 60
) -> tuple[dict[int, float], dict[int, list[str]]]:
    scores: dict[int, float] = {}
    channels: dict[int, list[str]] = {}
    for channel, identifiers, weight in rankings:
        for rank, identifier in enumerate(identifiers, start=1):
            scores[identifier] = scores.get(identifier, 0.0) + weight / (k + rank)
            channels.setdefault(identifier, []).append(channel)
    return scores, channels


class SearchService:
    def __init__(
        self,
        session: AsyncSession,
        client: httpx.AsyncClient,
        settings: Settings,
    ) -> None:
        self.session = session
        self.settings = settings
        self.repository = AIRepository(session)
        self.litellm = LiteLLMClient(client, settings)
        self.vectors = QdrantVectorStore(client, settings)

    async def search(
        self, query: str, *, mode: SearchMode, limit: int
    ) -> tuple[list[tuple[ContentItem, float, list[str]]], bool]:
        candidate_limit = min(limit * 4, 100)
        keyword_rows: list[tuple[ContentItem, float]] = []
        semantic_rows: list[tuple[int, float]] = []
        semantic_available = False

        if mode in {SearchMode.KEYWORD, SearchMode.HYBRID}:
            keyword_rows = await self.repository.keyword_search(query, limit=candidate_limit)
        if mode in {SearchMode.SEMANTIC, SearchMode.HYBRID}:
            semantic_started = monotonic()
            try:
                embedding = await self.litellm.embed(query)
                await self.repository.add_usage(
                    AIUsageEvent(
                        operation="search_embedding",
                        model_alias=embedding.usage.model_alias,
                        provider_request_id=embedding.usage.provider_request_id,
                        input_tokens=embedding.usage.input_tokens,
                        output_tokens=embedding.usage.output_tokens,
                        total_tokens=embedding.usage.total_tokens,
                        cost_usd=embedding.usage.cost_usd,
                        latency_ms=embedding.usage.latency_ms,
                        status="succeeded",
                        metadata_json={"query_characters": len(query)},
                    )
                )
                await self.session.commit()
                vector_rows = await self.vectors.search(
                    embedding.vector, limit=candidate_limit
                )
                semantic_rows = vector_rows or []
                semantic_available = vector_rows is not None
            except AIServiceError as exc:
                await self.session.rollback()
                await self.repository.add_usage(
                    AIUsageEvent(
                        operation="search_embedding",
                        model_alias=self.settings.litellm_embedding_model,
                        latency_ms=int((monotonic() - semantic_started) * 1000),
                        status="failed",
                        error_code=exc.code,
                        metadata_json={"query_characters": len(query)},
                    )
                )
                await self.session.commit()
                if mode == SearchMode.SEMANTIC:
                    raise
                semantic_available = False

        if mode == SearchMode.KEYWORD:
            return [
                (item, max(score, 0.0), ["keyword"]) for item, score in keyword_rows[:limit]
            ], semantic_available

        semantic_ids = [identifier for identifier, _ in semantic_rows]
        if mode == SearchMode.SEMANTIC:
            items = await self.repository.searchable_by_ids(semantic_ids)
            return [
                (items[identifier], max(score, 0.0), ["semantic"])
                for identifier, score in semantic_rows
                if identifier in items
            ][:limit], semantic_available

        keyword_ids = [item.id for item, _ in keyword_rows]
        scores, channels = reciprocal_rank_fusion(
            (
                ("keyword", keyword_ids, 0.45),
                ("semantic", semantic_ids, 0.55),
            )
        )
        ordered_ids = sorted(scores, key=lambda identifier: scores[identifier], reverse=True)
        items = {item.id: item for item, _ in keyword_rows}
        items.update(await self.repository.searchable_by_ids(semantic_ids))
        return [
            (items[identifier], scores[identifier], channels[identifier])
            for identifier in ordered_ids
            if identifier in items
        ][:limit], semantic_available
