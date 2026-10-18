"""AI enrichment, cost tracking, and keyword search

Revision ID: 202610150004
Revises: 202610150003
Create Date: 2026-10-15 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202610150004"
down_revision: str | None = "202610150003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_enrichments",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "content_id",
            sa.BigInteger(),
            sa.ForeignKey("content_items.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column(
            "topics", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "skills", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "career_paths",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("difficulty", sa.Text()),
        sa.Column("quality_score", sa.Numeric(5, 4)),
        sa.Column(
            "quality_signals",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("moderation_status", sa.Text()),
        sa.Column(
            "moderation_categories",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("moderation_rationale", sa.Text()),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("model_alias", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("input_fingerprint", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.Text()),
        sa.Column("embedding_dimensions", sa.Integer()),
        sa.Column("vector_point_id", sa.Text()),
        sa.Column("error_code", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'review_required', 'failed', 'skipped')",
            name="ck_content_enrichments_status",
        ),
        sa.CheckConstraint(
            "difficulty IS NULL OR difficulty IN ('beginner', 'intermediate', 'advanced', 'mixed')",
            name="ck_content_enrichments_difficulty",
        ),
        sa.CheckConstraint(
            "moderation_status IS NULL OR moderation_status IN ('safe', 'review', 'reject')",
            name="ck_content_enrichments_moderation",
        ),
        sa.CheckConstraint(
            "quality_score IS NULL OR quality_score BETWEEN 0 AND 1",
            name="ck_content_enrichments_quality",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="ck_content_enrichments_confidence",
        ),
        sa.CheckConstraint(
            "embedding_dimensions IS NULL OR embedding_dimensions > 0",
            name="ck_content_enrichments_dimensions",
        ),
        sa.CheckConstraint("jsonb_typeof(topics) = 'array'", name="ck_content_enrichments_topics"),
        sa.CheckConstraint("jsonb_typeof(skills) = 'array'", name="ck_content_enrichments_skills"),
        sa.CheckConstraint(
            "jsonb_typeof(career_paths) = 'array'", name="ck_content_enrichments_career_paths"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(quality_signals) = 'object'",
            name="ck_content_enrichments_quality_signals",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(moderation_categories) = 'array'",
            name="ck_content_enrichments_moderation_categories",
        ),
    )
    op.create_index("ix_content_enrichments_status_id", "content_enrichments", ["status", "id"])
    op.create_index(
        "ix_content_enrichments_quality",
        "content_enrichments",
        [sa.text("quality_score DESC"), "content_id"],
        postgresql_where=sa.text("status = 'completed'"),
    )

    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "content_id",
            sa.BigInteger(),
            sa.ForeignKey("content_items.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "enrichment_id",
            sa.BigInteger(),
            sa.ForeignKey("content_enrichments.id", ondelete="SET NULL"),
        ),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("model_alias", sa.Text(), nullable=False),
        sa.Column("provider_request_id", sa.Text()),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_usd", sa.Numeric(14, 8)),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text()),
        sa.Column(
            "metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "operation IN ('content_analysis', 'content_embedding', 'search_embedding')",
            name="ck_ai_usage_events_operation",
        ),
        sa.CheckConstraint("status IN ('succeeded', 'failed')", name="ck_ai_usage_events_status"),
        sa.CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0 AND total_tokens >= 0 AND latency_ms >= 0",
            name="ck_ai_usage_events_counts",
        ),
        sa.CheckConstraint("cost_usd IS NULL OR cost_usd >= 0", name="ck_ai_usage_events_cost"),
        sa.CheckConstraint("jsonb_typeof(metadata) = 'object'", name="ck_ai_usage_events_metadata"),
    )
    op.create_index(
        "ix_ai_usage_events_created", "ai_usage_events", [sa.text("created_at DESC"), "id"]
    )
    op.create_index(
        "ix_ai_usage_events_operation_created",
        "ai_usage_events",
        ["operation", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_content_items_search_document",
        "content_items",
        [
            sa.text(
                "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))"
            )
        ],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_content_items_search_document", table_name="content_items")
    op.drop_index("ix_ai_usage_events_operation_created", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_created", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
    op.drop_index("ix_content_enrichments_quality", table_name="content_enrichments")
    op.drop_index("ix_content_enrichments_status_id", table_name="content_enrichments")
    op.drop_table("content_enrichments")
