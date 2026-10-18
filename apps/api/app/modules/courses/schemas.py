from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class CourseCreate(BaseModel):
    source_id: int = Field(gt=0)
    external_id: str | None = Field(default=None, max_length=500)
    canonical_url: HttpUrl
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    provider_name: str | None = Field(default=None, max_length=300)
    language_code: str | None = Field(default=None, min_length=2, max_length=10)
    thumbnail_url: HttpUrl | None = None
    published_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
