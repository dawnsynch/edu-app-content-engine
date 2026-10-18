"""dynamic content aggregation engine

Revision ID: 202610150003
Revises: 202610150002
Create Date: 2026-10-15 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202610150003"
down_revision: str | None = "202610150002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column(
            "connector_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_sources_connector_config_object",
        "sources",
        "jsonb_typeof(connector_config) = 'object'",
    )
    op.drop_constraint("ck_sources_source_type", "sources", type_="check")
    op.create_check_constraint(
        "ck_sources_source_type",
        "sources",
        "source_type IN "
        "('website', 'rss', 'api', 'owned_cms', 'youtube', 'repository', 'course_provider')",
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "source_id",
            sa.BigInteger(),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "checkpoint_before",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("checkpoint_after", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("discovered_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unchanged_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rejected_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "trigger IN ('manual', 'scheduled', 'retry')",
            name="ck_ingestion_runs_trigger",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'skipped')",
            name="ck_ingestion_runs_status",
        ),
        sa.CheckConstraint("attempt >= 1", name="ck_ingestion_runs_attempt"),
        sa.CheckConstraint(
            "discovered_count >= 0 AND created_count >= 0 AND updated_count >= 0 "
            "AND unchanged_count >= 0 AND rejected_count >= 0",
            name="ck_ingestion_runs_counts",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(checkpoint_before) = 'object'",
            name="ck_ingestion_runs_checkpoint_before_object",
        ),
        sa.CheckConstraint(
            "checkpoint_after IS NULL OR jsonb_typeof(checkpoint_after) = 'object'",
            name="ck_ingestion_runs_checkpoint_after_object",
        ),
    )
    op.create_index("ix_ingestion_runs_source_id_id", "ingestion_runs", ["source_id", "id"])
    op.create_index(
        "ix_ingestion_runs_status_created",
        "ingestion_runs",
        ["status", sa.text("created_at DESC")],
    )

    op.create_table(
        "source_sync_states",
        sa.Column(
            "source_id",
            sa.BigInteger(),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "checkpoint",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("etag", sa.Text()),
        sa.Column("last_modified", sa.Text()),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True)),
        sa.Column("last_succeeded_at", sa.DateTime(timezone=True)),
        sa.Column("next_due_at", sa.DateTime(timezone=True)),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_successes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_status", sa.Text()),
        sa.Column("last_error_code", sa.Text()),
        sa.Column("last_error_message", sa.Text()),
        sa.Column("last_duration_ms", sa.Integer()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "consecutive_failures >= 0 AND total_successes >= 0 AND total_failures >= 0",
            name="ck_source_sync_states_counts",
        ),
        sa.CheckConstraint(
            "last_duration_ms IS NULL OR last_duration_ms >= 0",
            name="ck_source_sync_states_duration",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(checkpoint) = 'object'",
            name="ck_source_sync_states_checkpoint_object",
        ),
    )
    op.create_index(
        "ix_source_sync_states_next_due",
        "source_sync_states",
        ["next_due_at", "source_id"],
    )
    op.create_index(
        "ix_source_sync_states_unhealthy",
        "source_sync_states",
        ["consecutive_failures", "source_id"],
        postgresql_where=sa.text("consecutive_failures > 0"),
    )


def downgrade() -> None:
    op.drop_index("ix_source_sync_states_unhealthy", table_name="source_sync_states")
    op.drop_index("ix_source_sync_states_next_due", table_name="source_sync_states")
    op.drop_table("source_sync_states")
    op.drop_index("ix_ingestion_runs_status_created", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_source_id_id", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    op.drop_constraint("ck_sources_source_type", "sources", type_="check")
    op.create_check_constraint(
        "ck_sources_source_type",
        "sources",
        "source_type IN ('website', 'rss', 'api', 'youtube', 'repository', 'course_provider')",
    )
    op.drop_constraint("ck_sources_connector_config_object", "sources", type_="check")
    op.drop_column("sources", "connector_config")
