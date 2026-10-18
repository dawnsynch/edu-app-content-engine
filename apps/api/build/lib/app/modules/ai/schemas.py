from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Difficulty(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    MIXED = "mixed"


class ModerationStatus(StrEnum):
    SAFE = "safe"
    REVIEW = "review"
    REJECT = "reject"


class ReviewAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class QualitySignals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completeness: float = Field(ge=0, le=1)
    clarity: float = Field(ge=0, le=1)
    authority: float = Field(ge=0, le=1)
    freshness: float = Field(ge=0, le=1)
    educational_value: float = Field(ge=0, le=1)


class QualityAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0, le=1)
    signals: QualitySignals


class ModerationAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ModerationStatus
    categories: list[str] = Field(max_length=10)
    rationale: str = Field(min_length=1, max_length=1000)


class EnrichmentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topics: list[str] = Field(min_length=1, max_length=8)
    skills: list[str] = Field(max_length=12)
    career_paths: list[str] = Field(max_length=8)
    difficulty: Difficulty
    quality: QualityAssessment
    moderation: ModerationAssessment
    confidence: float = Field(ge=0, le=1)

    @field_validator("topics", "skills", "career_paths")
    @classmethod
    def normalize_labels(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for item in values:
            normalized = " ".join(item.strip().lower().split())[:100]
            if normalized and normalized not in result:
                result.append(normalized)
        return result


class ModelUsage(BaseModel):
    model_alias: str
    provider_request_id: str | None = None
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost_usd: Decimal | None = Field(default=None, ge=0)
    latency_ms: int = Field(ge=0)


class AnalysisResult(BaseModel):
    decision: EnrichmentDecision
    usage: ModelUsage


class EmbeddingResult(BaseModel):
    vector: list[float] = Field(min_length=1)
    usage: ModelUsage


class EnrichmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content_id: int
    status: str
    topics: list[str]
    skills: list[str]
    career_paths: list[str]
    difficulty: Difficulty | None
    quality_score: Decimal | None
    quality_signals: dict[str, Any]
    moderation_status: ModerationStatus | None
    moderation_categories: list[str]
    moderation_rationale: str | None
    confidence: Decimal | None
    model_alias: str
    prompt_version: str
    schema_version: str
    embedding_model: str | None
    embedding_dimensions: int | None
    error_code: str | None
    error_message: str | None
    review_decision: str | None
    review_note: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EnrichmentTaskResponse(BaseModel):
    content_id: int
    task_id: str
    status: str = "queued"


class EnrichmentListResponse(BaseModel):
    items: list[EnrichmentResponse]
    next_cursor: int | None


class ReviewDecisionRequest(BaseModel):
    action: ReviewAction
    reviewer: str = Field(min_length=2, max_length=200)
    note: str = Field(min_length=2, max_length=2000)


class UsageEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content_id: int | None
    enrichment_id: int | None
    operation: str
    model_alias: str
    provider_request_id: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: Decimal | None
    latency_ms: int
    status: str
    error_code: str | None
    metadata_json: dict[str, Any]
    created_at: datetime


class UsageSummaryResponse(BaseModel):
    items: list[UsageEventResponse]
    request_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    reported_cost_usd: Decimal
    events_without_reported_cost: int
