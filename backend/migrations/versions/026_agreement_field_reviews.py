"""Per-row field decisions for the GM Compare table (per-row approve/reject,
2026-08-26 client feedback). Scoped to workflow_step_id, not just
agreement_id, so a decision doesn't leak across a resubmit-restarted review
cycle (see resubmit_agreement).

Revision ID: 026_agreement_field_reviews
Revises: 025_pdc_dlp_days_number_inputs
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "026_agreement_field_reviews"
down_revision: str | None = "025_pdc_dlp_days_number_inputs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agreement_field_reviews",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agreement_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("agreements.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "workflow_step_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("workflow_steps.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("field_id", sa.String(20), nullable=False, index=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("comment_text", sa.Text(), nullable=True),
        sa.Column(
            "decided_by",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="agreement_field_reviews_status_chk",
        ),
        sa.UniqueConstraint("workflow_step_id", "field_id", name="uq_field_review_step_field"),
    )


def downgrade() -> None:
    op.drop_table("agreement_field_reviews")
