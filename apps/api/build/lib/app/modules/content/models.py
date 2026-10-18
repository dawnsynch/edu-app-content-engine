from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    external_id: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    content_fingerprint: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="validated")
    author_name: Mapped[str | None] = mapped_column(Text)
    language_code: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
