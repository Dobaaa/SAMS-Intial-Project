"""Appendix display polish.

1. C10 / A19 (Defects Liability Period): change input_type from 'number' to
   'text' so admin can type "12 months" or "365 days" instead of a bare integer.

Revision ID: 016_appendix_polish
Revises: 015_hide_a05
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "016_appendix_polish"
down_revision: str | None = "015_hide_a05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET input_type = 'text' "
            "WHERE field_id IN ('C10', 'A19')"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET input_type = 'number' "
            "WHERE field_id IN ('C10', 'A19')"
        )
    )
