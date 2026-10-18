from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.modules.content.enums import ContentType


class ContentCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str | None = Field(default=None, max_length=500)
    canonical_url: HttpUrl
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    content_type: ContentType
    author_name: str | None = Field(default=None, max_length=300)
    language_code: str | None = Field(default=None, min_length=2, max_length=10)
    thumbnail_url: HttpUrl | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    published_at: datetime | None = None
    provider_updated_at: datetime | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class ConnectorContext(BaseModel):
    source_id: int
    base_url: HttpUrl
    allowed_domains: list[str] = Field(default_factory=list)
    connector_config: dict[str, Any] = Field(default_factory=dict)
    checkpoint: dict[str, Any] = Field(default_factory=dict)
    etag: str | None = None
    last_modified: str | None = None


class ConnectorResult(BaseModel):
    items: list[ContentCandidate] = Field(default_factory=list)
    checkpoint: dict[str, Any] = Field(default_factory=dict)
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False


class Connector(Protocol):
    async def fetch(self, context: ConnectorContext) -> ConnectorResult: ...
