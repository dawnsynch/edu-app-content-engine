from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.content.enums import ContentType
from app.modules.recommendations.enums import EngagementType, SkillLevel


def _normalize_labels(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        label = " ".join(value.strip().lower().split())[:100]
        if label and label not in normalized:
            normalized.append(label)
    return normalized


class LearnerProfileCreate(BaseModel):
    career_preferences: list[str] = Field(default_factory=list, max_length=10)
    technology_domains: list[str] = Field(default_factory=list, max_length=12)
    skill_level: SkillLevel = SkillLevel.BEGINNER

    @field_validator("career_preferences", "technology_domains")
    @classmethod
    def normalize_labels(cls, values: list[str]) -> list[str]:
        return _normalize_labels(values)


class LearnerProfileUpdate(BaseModel):
    career_preferences: list[str] | None = Field(default=None, max_length=10)
    technology_domains: list[str] | None = Field(default=None, max_length=12)
    skill_level: SkillLevel | None = None

    @field_validator("career_preferences", "technology_domains")
    @classmethod
    def normalize_labels(cls, values: list[str] | None) -> list[str] | None:
        return _normalize_labels(values) if values is not None else None


class LearnerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    career_preferences: list[str]
    technology_domains: list[str]
    skill_level: SkillLevel
    recommendation_version: int
    created_at: datetime
    updated_at: datetime


class SignalResponse(BaseModel):
    learner_id: UUID
    content_id: int
    bookmarked: bool
    dismissed: bool


class BookmarkItem(BaseModel):
    signal_id: int
    content: "RecommendationContent"


class BookmarkListResponse(BaseModel):
    items: list[BookmarkItem]
    next_cursor: int | None


class EngagementCreate(BaseModel):
    content_id: int = Field(gt=0)
    event_type: EngagementType
    dwell_seconds: int | None = Field(default=None, ge=0, le=86400)


class EngagementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    learner_id: UUID
    content_id: int
    event_type: EngagementType
    dwell_seconds: int | None
    occurred_at: datetime


class RecommendationContent(BaseModel):
    id: int
    source_id: int
    source_name: str
    attribution: str | None
    canonical_url: str
    title: str
    description: str | None
    content_type: ContentType
    author_name: str | None
    language_code: str | None
    thumbnail_url: str | None
    duration_seconds: int | None
    published_at: datetime | None


class ScoreComponent(BaseModel):
    weight: float
    value: float
    contribution: float
    reason: str


class ScoreExplanation(BaseModel):
    components: dict[str, ScoreComponent]
    matched_careers: list[str]
    matched_domains: list[str]
    interaction_signals: list[str]


class RecommendationItem(BaseModel):
    content: RecommendationContent
    score: float = Field(ge=0, le=1)
    explanation: ScoreExplanation


class RecommendationResponse(BaseModel):
    learner_id: UUID
    recommendation_version: int
    cold_start: bool
    diversity_applied: bool
    items: list[RecommendationItem]
    next_cursor: str | None
