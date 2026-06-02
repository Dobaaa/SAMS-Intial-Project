"""Move A24/A25/A26 from appendix summary rows to inline milestone-table tokens.

The three material-submission / shop-drawing fields should render via
{{A24}}/{{A25}}/{{A26}} tokens inside the page-22 milestone table (Table 5),
NOT as standalone rows in the appendix summary table (Table 3).

This migration sets show_in_appendix=False for A24/A25/A26 so the AppendixBuilder
no longer renders them as summary rows. Values are still entered via the
AppendixBuilder UI and substituted into the milestone table via tokens.

The master docx is corrected by:
  python backend/scripts/apply_master_milestone_table_patch.py

Revision ID: 014_milestone_table_tokens
Revises: 013_material_fields
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014_milestone_table_tokens"
down_revision: str | None = "013_material_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET show_in_appendix = false "
            "WHERE field_id IN ('A24', 'A25', 'A26')"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET show_in_appendix = true "
            "WHERE field_id IN ('A24', 'A25', 'A26')"
        )
    )
