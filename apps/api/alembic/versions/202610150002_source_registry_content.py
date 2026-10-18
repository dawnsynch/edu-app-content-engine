"""source registry and normalized content

Revision ID: 202610150002
Revises: 202610130001
Create Date: 2026-10-15 12:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202610150002"
down_revision: str | None = "202610130001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column(
            "allowed_domains",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("rights_status", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("storage_mode", sa.Text(), server_default="metadata_only", nullable=False),
        sa.Column("terms_url", sa.Text()),
        sa.Column("license_name", sa.Text()),
        sa.Column("attribution_required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("attribution_text", sa.Text()),
        sa.Column("retention_days", sa.Integer()),
        sa.Column("fetch_interval_minutes", sa.Integer(), server_default="1440", nullable=False),
        sa.Column("respect_robots_txt", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("allow_summaries", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("allow_embeddings", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("allow_snippets", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("allow_thumbnails", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "policy_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("rights_reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("rights_review_due_at", sa.DateTime(timezone=True)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "source_type IN ('website', 'rss', 'api', 'youtube', 'repository', 'course_provider')",
            name="ck_sources_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'paused', 'blocked')",
            name="ck_sources_status",
        ),
        sa.CheckConstraint(
            "rights_status IN "
            "('unknown', 'review_required', 'approved', 'restricted', 'prohibited')",
            name="ck_sources_rights_status",
        ),
        sa.CheckConstraint(
            "storage_mode IN ('metadata_only', 'snippet', 'full_text')",
            name="ck_sources_storage_mode",
        ),
        sa.CheckConstraint(
            "retention_days IS NULL OR retention_days BETWEEN 1 AND 3650",
            name="ck_sources_retention_days",
        ),
        sa.CheckConstraint(
            "fetch_interval_minutes BETWEEN 5 AND 525600",
            name="ck_sources_fetch_interval",
        ),
        sa.CheckConstraint(
            "NOT attribution_required OR attribution_text IS NOT NULL",
            name="ck_sources_attribution",
        ),
        sa.CheckConstraint(
            "status <> 'active' OR rights_status IN ('approved', 'restricted')",
            name="ck_sources_active_rights",
        ),
        sa.CheckConstraint(
            "rights_status <> 'prohibited' OR "
            "(status <> 'active' AND NOT allow_summaries AND NOT allow_embeddings "
            "AND NOT allow_snippets AND NOT allow_thumbnails)",
            name="ck_sources_prohibited_rights",
        ),
        sa.CheckConstraint(
            "storage_mode <> 'full_text' OR rights_status = 'approved'",
            name="ck_sources_full_text_rights",
        ),
        sa.CheckConstraint(
            "storage_mode <> 'metadata_only' OR NOT allow_snippets",
            name="ck_sources_metadata_only",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(allowed_domains) = 'array'",
            name="ck_sources_allowed_domains_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(policy_metadata) = 'object'",
            name="ck_sources_policy_metadata_object",
        ),
        sa.CheckConstraint(
            "rights_review_due_at IS NULL OR rights_reviewed_at IS NULL "
            "OR rights_review_due_at > rights_reviewed_at",
            name="ck_sources_review_dates",
        ),
        sa.UniqueConstraint("slug", name="uq_sources_slug"),
        sa.UniqueConstraint("base_url", name="uq_sources_base_url"),
    )
    op.create_index(
        "ix_sources_active_status_id",
        "sources",
        ["status", "id"],
        unique=False,
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.create_index(
        "ix_sources_rights_review_due",
        "sources",
        ["rights_review_due_at"],
        unique=False,
        postgresql_where=sa.text("rights_review_due_at IS NOT NULL AND archived_at IS NULL"),
    )

    op.create_table(
        "content_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "source_id",
            sa.BigInteger(),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("external_id", sa.Text()),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("content_fingerprint", sa.Text()),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="validated", nullable=False),
        sa.Column("author_name", sa.Text()),
        sa.Column("language_code", sa.Text()),
        sa.Column("thumbnail_url", sa.Text()),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("provider_updated_at", sa.DateTime(timezone=True)),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True)),
        sa.Column(
            "raw_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "content_type IN "
            "('article', 'video', 'course', 'tutorial', 'podcast', 'repository', "
            "'documentation', 'event', 'other')",
            name="ck_content_items_type",
        ),
        sa.CheckConstraint(
            "status IN ('discovered', 'validated', 'rejected', 'expired')",
            name="ck_content_items_status",
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_content_items_duration",
        ),
        sa.CheckConstraint(
            "language_code IS NULL OR char_length(language_code) BETWEEN 2 AND 10",
            name="ck_content_items_language",
        ),
        sa.CheckConstraint(
            "content_fingerprint IS NULL OR content_fingerprint ~ '^[a-f0-9]{64}$'",
            name="ck_content_items_fingerprint",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(raw_metadata) = 'object'",
            name="ck_content_items_raw_metadata_object",
        ),
        sa.UniqueConstraint("canonical_url", name="uq_content_items_canonical_url"),
    )
    op.create_index(
        "ix_content_items_source_id_id",
        "content_items",
        ["source_id", "id"],
        unique=False,
    )
    op.create_index(
        "uq_content_items_source_external_id",
        "content_items",
        ["source_id", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.create_index(
        "uq_content_items_fingerprint",
        "content_items",
        ["content_fingerprint"],
        unique=True,
        postgresql_where=sa.text("content_fingerprint IS NOT NULL"),
    )
    op.create_index(
        "ix_content_items_status_published_id",
        "content_items",
        ["status", sa.text("published_at DESC"), "id"],
        unique=False,
    )
    op.create_index(
        "ix_content_items_retention_expires",
        "content_items",
        ["retention_expires_at"],
        unique=False,
        postgresql_where=sa.text("retention_expires_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_content_items_retention_expires", table_name="content_items")
    op.drop_index("ix_content_items_status_published_id", table_name="content_items")
    op.drop_index("uq_content_items_fingerprint", table_name="content_items")
    op.drop_index("uq_content_items_source_external_id", table_name="content_items")
    op.drop_index("ix_content_items_source_id_id", table_name="content_items")
    op.drop_table("content_items")
    op.drop_index("ix_sources_rights_review_due", table_name="sources")
    op.drop_index("ix_sources_active_status_id", table_name="sources")
    op.drop_table("sources")
