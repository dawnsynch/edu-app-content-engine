from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from time import monotonic

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PolicyViolationError, ResourceNotFoundError
from app.core.settings import Settings
from app.modules.ai.client import LiteLLMClient
from app.modules.ai.errors import AIServiceError
from app.modules.ai.models import AIUsageEvent, ContentEnrichment
from app.modules.ai.qdrant import QdrantVectorStore
from app.modules.ai.repository import AIRepository
from app.modules.ai.schemas import (
    EnrichmentDecision,
    ModelUsage,
    ReviewAction,
    ReviewDecisionRequest,
)
from app.modules.ai.temporal import (
    PublicationContext,
    enforce_publication_policy,
    evaluate_publication_date,
)
from app.modules.content.models import ContentItem
from app.modules.sources.models import Source


def enrichment_fingerprint(content: ContentItem, settings: Settings) -> str:
    values = (
        content.title,
        content.description or "",
        content.content_type,
        content.author_name or "",
        content.provider_updated_at.isoformat() if content.provider_updated_at else "",
        settings.litellm_model,
        settings.litellm_embedding_model,
        settings.ai_prompt_version,
        settings.ai_schema_version,
    )
    return sha256("\x1f".join(values).encode()).hexdigest()


def embedding_text(content: ContentItem) -> str:
    values = [content.title, content.description or "", content.content_type]
    return "\n".join(value for value in values if value).strip()


class AIEnrichmentService:
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

    async def get(self, content_id: int) -> ContentEnrichment:
        enrichment = await self.repository.get_enrichment(content_id)
        if enrichment is None:
            raise ResourceNotFoundError("content enrichment not found")
        return enrichment

    async def pending_content_ids(self) -> list[int]:
        return await self.repository.pending_content_ids(
            limit=self.settings.enrichment_batch_size,
            model_alias=self.settings.litellm_model,
            embedding_model=self.settings.litellm_embedding_model,
            prompt_version=self.settings.ai_prompt_version,
            schema_version=self.settings.ai_schema_version,
        )

    async def enrich(self, content_id: int) -> ContentEnrichment:
        context = await self.repository.get_context(content_id)
        if context is None:
            raise ResourceNotFoundError("content item not found")
        content, source = context
        self._validate_eligibility(content, source)
        fingerprint = enrichment_fingerprint(content, self.settings)
        enrichment = await self.repository.get_enrichment(content_id)
        if enrichment is not None and self._is_current(enrichment, fingerprint, source):
            return enrichment
        if enrichment is None:
            enrichment = await self.repository.add_enrichment(
                ContentEnrichment(
                    content_id=content.id,
                    model_alias=self.settings.litellm_model,
                    prompt_version=self.settings.ai_prompt_version,
                    schema_version=self.settings.ai_schema_version,
                    input_fingerprint=fingerprint,
                )
            )

        if source.policy_metadata.get("allow_ai_enrichment") is False:
            enrichment.status = "skipped"
            enrichment.error_code = "source_policy_opt_out"
            enrichment.error_message = "source policy disables AI enrichment"
            enrichment.completed_at = datetime.now(UTC)
            await self.session.commit()
            await self.session.refresh(enrichment)
            return enrichment

        enrichment.status = "running"
        enrichment.model_alias = self.settings.litellm_model
        enrichment.prompt_version = self.settings.ai_prompt_version
        enrichment.schema_version = self.settings.ai_schema_version
        enrichment.input_fingerprint = fingerprint
        enrichment.started_at = datetime.now(UTC)
        enrichment.completed_at = None
        enrichment.error_code = None
        enrichment.error_message = None
        await self.session.commit()

        operation = "content_analysis"
        started = monotonic()
        try:
            temporal_context = evaluate_publication_date(content.published_at)
            analysis = await self.litellm.analyze(
                self._analysis_payload(content, source, temporal_context)
            )
            await self._record_usage(
                analysis.usage,
                operation=operation,
                content_id=content.id,
                enrichment_id=enrichment.id,
            )
            decision = enforce_publication_policy(analysis.decision, temporal_context)
            self._apply_decision(enrichment, decision)

            approved = (
                decision.moderation.status.value == "safe"
                and decision.confidence >= self.settings.ai_min_confidence
            )
            if approved and source.allow_embeddings:
                operation = "content_embedding"
                embedded = await self.litellm.embed(embedding_text(content))
                await self._record_usage(
                    embedded.usage,
                    operation=operation,
                    content_id=content.id,
                    enrichment_id=enrichment.id,
                )
                await self.vectors.upsert(
                    point_id=content.id,
                    vector=embedded.vector,
                    payload={
                        "content_id": content.id,
                        "source_id": content.source_id,
                        "content_type": content.content_type,
                    },
                )
                enrichment.embedding_model = self.settings.litellm_embedding_model
                enrichment.embedding_dimensions = len(embedded.vector)
                enrichment.vector_point_id = str(content.id)
            elif enrichment.vector_point_id is not None:
                await self.vectors.delete(content.id)
                enrichment.embedding_model = None
                enrichment.embedding_dimensions = None
                enrichment.vector_point_id = None

            enrichment.status = "completed" if approved else "review_required"
            enrichment.completed_at = datetime.now(UTC)
            await self.session.commit()
            await self.session.refresh(enrichment)
            return enrichment
        except AIServiceError as exc:
            await self.repository.add_usage(
                AIUsageEvent(
                    content_id=content.id,
                    enrichment_id=enrichment.id,
                    operation=operation,
                    model_alias=(
                        self.settings.litellm_embedding_model
                        if operation == "content_embedding"
                        else self.settings.litellm_model
                    ),
                    latency_ms=int((monotonic() - started) * 1000),
                    status="failed",
                    error_code=exc.code,
                    metadata_json={},
                )
            )
            enrichment.status = "failed"
            enrichment.error_code = exc.code
            enrichment.error_message = str(exc)[:2000]
            enrichment.completed_at = datetime.now(UTC)
            await self.session.commit()
            raise

    async def list_review_queue(
        self, *, after_id: int | None, limit: int
    ) -> tuple[list[ContentEnrichment], int | None]:
        rows = await self.repository.list_review_queue(after_id=after_id, limit=limit)
        has_more = len(rows) > limit
        items = rows[:limit]
        return items, items[-1].id if has_more and items else None

    async def review(self, content_id: int, decision: ReviewDecisionRequest) -> ContentEnrichment:
        context = await self.repository.get_context(content_id)
        if context is None:
            raise ResourceNotFoundError("content item not found")
        content, source = context
        self._validate_eligibility(content, source)
        enrichment = await self.get(content_id)
        if enrichment.status != "review_required":
            raise PolicyViolationError("content is not awaiting moderation review")

        if decision.action == ReviewAction.APPROVE:
            if source.allow_embeddings and enrichment.vector_point_id is None:
                embedded = await self.litellm.embed(embedding_text(content))
                await self._record_usage(
                    embedded.usage,
                    operation="content_embedding",
                    content_id=content.id,
                    enrichment_id=enrichment.id,
                    metadata={"trigger": "moderation_approval"},
                )
                await self.vectors.upsert(
                    point_id=content.id,
                    vector=embedded.vector,
                    payload={
                        "content_id": content.id,
                        "source_id": content.source_id,
                        "content_type": content.content_type,
                    },
                )
                enrichment.embedding_model = self.settings.litellm_embedding_model
                enrichment.embedding_dimensions = len(embedded.vector)
                enrichment.vector_point_id = str(content.id)
            enrichment.status = "completed"
            enrichment.moderation_status = "safe"
            enrichment.review_decision = "approved"
        else:
            if enrichment.vector_point_id is not None:
                await self.vectors.delete(content.id)
            enrichment.embedding_model = None
            enrichment.embedding_dimensions = None
            enrichment.vector_point_id = None
            enrichment.status = "skipped"
            enrichment.moderation_status = "reject"
            enrichment.review_decision = "rejected"

        enrichment.review_note = decision.note
        enrichment.reviewed_by = decision.reviewer
        enrichment.reviewed_at = datetime.now(UTC)
        enrichment.completed_at = enrichment.reviewed_at
        await self.session.commit()
        await self.session.refresh(enrichment)
        return enrichment

    async def _record_usage(
        self,
        usage: ModelUsage,
        *,
        operation: str,
        content_id: int | None,
        enrichment_id: int | None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        await self.repository.add_usage(
            AIUsageEvent(
                content_id=content_id,
                enrichment_id=enrichment_id,
                operation=operation,
                model_alias=usage.model_alias,
                provider_request_id=usage.provider_request_id,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
                cost_usd=usage.cost_usd,
                latency_ms=usage.latency_ms,
                status="succeeded",
                metadata_json=metadata or {},
            )
        )
        await self.session.commit()

    @staticmethod
    def _analysis_payload(
        content: ContentItem,
        source: Source,
        temporal_context: PublicationContext,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "title": content.title,
            "description": content.description,
            "content_type": content.content_type,
            "author_name": content.author_name,
            "published_at": content.published_at.isoformat() if content.published_at else None,
            "source_name": source.name,
            "source_rights_status": source.rights_status,
        }
        payload.update(temporal_context.as_prompt_fields())
        return payload

    @staticmethod
    def _apply_decision(enrichment: ContentEnrichment, decision: EnrichmentDecision) -> None:
        enrichment.topics = decision.topics
        enrichment.skills = decision.skills
        enrichment.career_paths = decision.career_paths
        enrichment.difficulty = decision.difficulty.value
        enrichment.quality_score = Decimal(str(decision.quality.score))
        enrichment.quality_signals = decision.quality.signals.model_dump()
        enrichment.moderation_status = decision.moderation.status.value
        enrichment.moderation_categories = decision.moderation.categories
        enrichment.moderation_rationale = decision.moderation.rationale
        enrichment.confidence = Decimal(str(decision.confidence))

    @staticmethod
    def _validate_eligibility(content: ContentItem, source: Source) -> None:
        now = datetime.now(UTC)
        if source.status != "active" or source.rights_status not in {
            "approved",
            "restricted",
        }:
            raise PolicyViolationError("AI enrichment requires active approved source rights")
        if source.rights_review_due_at and source.rights_review_due_at <= now:
            raise PolicyViolationError("source rights review is overdue")
        if content.status != "validated":
            raise PolicyViolationError("AI enrichment requires validated content")
        if content.retention_expires_at and content.retention_expires_at <= now:
            raise PolicyViolationError("content retention period has expired")

    @staticmethod
    def _is_current(
        enrichment: ContentEnrichment,
        fingerprint: str,
        source: Source,
    ) -> bool:
        complete = enrichment.status in {"completed", "review_required", "skipped"}
        embedding_current = (
            enrichment.status != "completed"
            or not source.allow_embeddings
            or enrichment.vector_point_id is not None
        )
        return complete and enrichment.input_fingerprint == fingerprint and embedding_current
