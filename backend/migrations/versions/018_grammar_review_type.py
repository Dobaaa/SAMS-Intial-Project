"""Add 'grammar' value to review_type_enum.

Revision ID: 018_grammar_review_type
Revises: 017_rename_c02
Create Date: 2026-06-02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "018_grammar_review_type"
down_revision: str | None = "017_rename_c02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE review_type_enum ADD VALUE IF NOT EXISTS 'grammar'")


def downgrade() -> None:
    # Postgres does not support removing enum values; this is a no-op
    pass
