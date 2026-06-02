"""Hide A05 (Main Contractor communications address) from appendix.

The Communications Address section in the appendix now shows only the
Subcontractor address (A06). A05 row has been collapsed into the A06 row
in the master docx via apply_master_remove_a05_row_patch.py.

Revision ID: 015_hide_a05
Revises: 014_milestone_table_tokens
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "015_hide_a05"
down_revision: str | None = "014_milestone_table_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET show_in_appendix = false "
            "WHERE field_id = 'A05'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET show_in_appendix = true "
            "WHERE field_id = 'A05'"
        )
    )
