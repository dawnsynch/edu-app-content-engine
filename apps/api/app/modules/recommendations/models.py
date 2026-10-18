from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LearnerProfile(Base):
    __tablename__ = "learner_profiles"
    __table_args__ = (
        CheckConstraint(
            "skill_level IN ('beginner', 'intermediate', 'advanced')",
            name="ck_learner_profiles_skill_level",
        ),
        CheckConstraint(
            "recommendation_version > 0",
            name="ck_learner_profiles_recommendation_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    career_preferences: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    technology_domains: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    skill_level: Mapped[str] = mapped_column(Text, nullable=False, default="beginner")
    recommendation_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class LearnerContentSignal(Base):
    __tablename__ = "learner_content_signals"
    __table_args__ = (
        UniqueConstraint("learner_id", "content_id", name="uq_learner_content_signal"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    learner_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("learner_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False
    )
    bookmarked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class EngagementEvent(Base):
    __tablename__ = "engagement_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('view', 'click', 'start', 'complete')",
            name="ck_engagement_events_type",
        ),
        CheckConstraint(
            "dwell_seconds IS NULL OR dwell_seconds BETWEEN 0 AND 86400",
            name="ck_engagement_events_dwell",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    learner_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("learner_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    dwell_seconds: Mapped[int | None] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
