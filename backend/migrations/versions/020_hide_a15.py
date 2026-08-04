"""Hide A15 (Commencement Date) from appendix.

The Commencement Date row has been removed from the master docx Table 3 via
apply_master_remove_commencement_date_patch.py, and the clause-4.3 sentence
that referenced it has been reworded (Time for Completion is already a
day-count field, not date-anchored). Existing agreements keep their stored
A15 values and AppendixConfig rows untouched (show_in_appendix was already
True for them at creation time) so their historical PDFs are unaffected;
this only stops NEW agreements from collecting/showing A15 going forward.

Revision ID: 020_hide_a15
Revises: 019_comment_reactions
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "020_hide_a15"
down_revision: str | None = "019_comment_reactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET show_in_appendix = false "
            "WHERE field_id = 'A15'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET show_in_appendix = true "
            "WHERE field_id = 'A15'"
        )
    )
