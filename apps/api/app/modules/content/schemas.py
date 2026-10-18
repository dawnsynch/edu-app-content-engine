from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.modules.content.enums import ContentStatus, ContentType


class ContentCreate(BaseModel):
    source_id: int = Field(gt=0)
    external_id: str | None = Field(default=None, max_length=500)
    canonical_url: HttpUrl
    content_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
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

    @field_validator("language_code")
    @classmethod
    def normalize_language_code(cls, value: str | None) -> str | None:
        return value.lower() if value else None

    @model_validator(mode="after")
    def reject_rehosted_video_fields(self) -> "ContentCreate":
        if self.content_type != ContentType.VIDEO:
            return self
        forbidden = {"binary", "download_url", "local_path", "storage_key", "video_bytes"}
        present = forbidden.intersection(self.raw_metadata)
        if present:
            names = ", ".join(sorted(present))
            raise ValueError(f"external videos cannot include rehosted media fields: {names}")
        return self


class ContentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    external_id: str | None
    canonical_url: str
    content_fingerprint: str | None
    title: str
    description: str | None
    content_type: ContentType
    status: ContentStatus
    author_name: str | None
    language_code: str | None
    thumbnail_url: str | None
    duration_seconds: int | None
    published_at: datetime | None
    provider_updated_at: datetime | None
    retention_expires_at: datetime | None
    raw_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ContentListResponse(BaseModel):
    items: list[ContentResponse]
    next_cursor: int | None
