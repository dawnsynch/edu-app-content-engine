from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.modules.content.enums import ContentType


class SearchMode(StrEnum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class SearchContent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    canonical_url: str
    title: str
    description: str | None
    content_type: ContentType
    author_name: str | None
    language_code: str | None
    thumbnail_url: str | None
    duration_seconds: int | None
    published_at: datetime | None


class SearchResult(BaseModel):
    content: SearchContent
    score: float = Field(ge=0)
    matched_by: list[str]


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    semantic_available: bool
    items: list[SearchResult]
