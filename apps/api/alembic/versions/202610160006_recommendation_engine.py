"""anonymous learner recommendations and engagement signals

Revision ID: 202610160006
Revises: 202610150005
Create Date: 2026-10-16 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202610160006"
down_revision: str | None = "202610150005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learner_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column(
            "career_preferences",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "technology_domains",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("skill_level", sa.Text(), server_default="beginner", nullable=False),
        sa.Column("recommendation_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "skill_level IN ('beginner', 'intermediate', 'advanced')",
            name="ck_learner_profiles_skill_level",
        ),
        sa.CheckConstraint(
            "recommendation_version > 0",
            name="ck_learner_profiles_recommendation_version",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(career_preferences) = 'array'",
            name="ck_learner_profiles_careers",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(technology_domains) = 'array'",
            name="ck_learner_profiles_domains",
        ),
    )

    op.create_table(
        "learner_content_signals",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "learner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("learner_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "content_id",
            sa.BigInteger(),
            sa.ForeignKey("content_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bookmarked", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("dismissed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("learner_id", "content_id", name="uq_learner_content_signal"),
    )
    op.create_index(
        "ix_learner_content_signals_learner_id",
        "learner_content_signals",
        ["learner_id", "id"],
    )
    op.create_index(
        "ix_learner_content_signals_bookmarks",
        "learner_content_signals",
        ["learner_id", "id"],
        postgresql_where=sa.text("bookmarked = true"),
    )

    op.create_table(
        "engagement_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "learner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("learner_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "content_id",
            sa.BigInteger(),
            sa.ForeignKey("content_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("dwell_seconds", sa.Integer()),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "event_type IN ('view', 'click', 'start', 'complete')",
            name="ck_engagement_events_type",
        ),
        sa.CheckConstraint(
            "dwell_seconds IS NULL OR dwell_seconds BETWEEN 0 AND 86400",
            name="ck_engagement_events_dwell",
        ),
    )
    op.create_index(
        "ix_engagement_events_learner_content",
        "engagement_events",
        ["learner_id", "content_id", "event_type"],
    )
    op.create_index(
        "ix_engagement_events_occurred_at",
        "engagement_events",
        [sa.text("occurred_at DESC"), "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_engagement_events_occurred_at", table_name="engagement_events")
    op.drop_index("ix_engagement_events_learner_content", table_name="engagement_events")
    op.drop_table("engagement_events")
    op.drop_index("ix_learner_content_signals_bookmarks", table_name="learner_content_signals")
    op.drop_index("ix_learner_content_signals_learner_id", table_name="learner_content_signals")
    op.drop_table("learner_content_signals")
    op.drop_table("learner_profiles")
