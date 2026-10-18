"""moderation review audit

Revision ID: 202610150005
Revises: 202610150004
Create Date: 2026-10-15 20:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610150005"
down_revision: str | None = "202610150004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("content_enrichments", sa.Column("review_decision", sa.Text()))
    op.add_column("content_enrichments", sa.Column("review_note", sa.Text()))
    op.add_column("content_enrichments", sa.Column("reviewed_by", sa.Text()))
    op.add_column("content_enrichments", sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "ck_content_enrichments_review_decision",
        "content_enrichments",
        "review_decision IS NULL OR review_decision IN ('approved', 'rejected')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_content_enrichments_review_decision",
        "content_enrichments",
        type_="check",
    )
    op.drop_column("content_enrichments", "reviewed_at")
    op.drop_column("content_enrichments", "reviewed_by")
    op.drop_column("content_enrichments", "review_note")
    op.drop_column("content_enrichments", "review_decision")
