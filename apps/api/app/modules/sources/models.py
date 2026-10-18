from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Identity, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    allowed_domains: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    rights_status: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    storage_mode: Mapped[str] = mapped_column(Text, nullable=False, default="metadata_only")
    terms_url: Mapped[str | None] = mapped_column(Text)
    license_name: Mapped[str | None] = mapped_column(Text)
    attribution_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    attribution_text: Mapped[str | None] = mapped_column(Text)
    retention_days: Mapped[int | None] = mapped_column(Integer)
    fetch_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1440)
    respect_robots_txt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_summaries: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_embeddings: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_snippets: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_thumbnails: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    policy_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    connector_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    rights_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rights_review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
