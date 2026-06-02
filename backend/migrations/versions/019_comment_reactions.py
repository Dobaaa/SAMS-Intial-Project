"""Add comment_reactions table for role-hierarchy accept/reject.

Revision ID: 019_comment_reactions
Revises: 018_grammar_review_type
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "019_comment_reactions"
down_revision: str | None = "018_grammar_review_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "comment_reactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("comment_id", UUID(as_uuid=True), sa.ForeignKey("workflow_comments.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("reactor_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reactor_role", sa.String(50), nullable=False),
        sa.Column("reaction", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("comment_id", "reactor_user_id", name="uq_comment_reaction_user"),
    )


def downgrade() -> None:
    op.drop_table("comment_reactions")
