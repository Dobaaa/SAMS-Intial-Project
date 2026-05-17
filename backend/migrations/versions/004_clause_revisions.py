"""Per-agreement clause revisions (Rev 01 items 3 + 17-extension).

Phase 4 v2: admin can edit any clause prose in the master docx for a
specific agreement. Each edit is stored here as a revision with an
acceptance state (pending / accepted / rejected). At render time, the
PDF pipeline applies accepted revisions and (in v2.2) renders pending
revisions as Word-style track-changes inside the PDF.

Revision ID: 004_clause_revisions
Revises: 003_manual_override_flag
Create Date: 2026-05-17
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "004_clause_revisions"
down_revision: str | None = "003_manual_override_flag"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agreement_clause_revisions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agreement_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("agreements.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # SHA-256 of the original paragraph's text (trim + collapse whitespace)
        # at the time the revision was created. Acts as a stable anchor so we
        # can locate the paragraph in the master docx at render time without
        # depending on positional indices that shift when the master is
        # re-tokenized.
        sa.Column("clause_hash", sa.String(64), nullable=False, index=True),
        # Human-readable label shown in the revisions UI ("1.1 Definitions",
        # "1.5 Confidential Information (b)", "Appendix · The Subcontractor",
        # etc.). Captured at creation; never recomputed.
        sa.Column("clause_label", sa.String(255), nullable=False),
        # Verbatim text snapshot of the paragraph as it appeared in the
        # master at creation time. Kept so the revision survives even if
        # the master is later re-tokenized in a way that shifts the
        # paragraph text (the orphaned-revision case shows a "stale" badge).
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("modified_text", sa.Text(), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "created_by",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "decided_by",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name="agreement_clause_revisions_status_chk",
        ),
    )


def downgrade() -> None:
    op.drop_table("agreement_clause_revisions")
