from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContentEnrichment(Base):
    __tablename__ = "content_enrichments"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    content_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("content_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    topics: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    skills: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    career_paths: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    difficulty: Mapped[str | None] = mapped_column(Text)
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    quality_signals: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    moderation_status: Mapped[str | None] = mapped_column(Text)
    moderation_categories: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    moderation_rationale: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    model_alias: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer)
    vector_point_id: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    review_decision: Mapped[str | None] = mapped_column(Text)
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AIUsageEvent(Base):
    __tablename__ = "ai_usage_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    content_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("content_items.id", ondelete="SET NULL")
    )
    enrichment_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("content_enrichments.id", ondelete="SET NULL")
    )
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    model_alias: Mapped[str] = mapped_column(Text, nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 8))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
