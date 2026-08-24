"""Hide A15 (Commencement Date) and A16 (Time for Completion - Project) from
the appendix/portal; C08 no longer required; renumber A17/A18/A24-A26
appendix clause refs 4.3->4.2 to match the master docx's renumbered clauses.

Revision ID: 024_remove_commencement_date
Revises: 023_c08_label_in_days
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "024_remove_commencement_date"
down_revision: str | None = "023_c08_label_in_days"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET show_in_appendix = false WHERE field_id IN ('A15', 'A16')"
        )
    )
    op.execute(sa.text("UPDATE master_fields SET is_required = false WHERE field_id = 'C08'"))
    op.execute(
        sa.text("UPDATE master_fields SET appendix_clause_ref = '4.2(a)' WHERE field_id = 'A17'")
    )
    op.execute(
        sa.text(
            "UPDATE master_fields SET appendix_clause_ref = '4.2(b)' "
            "WHERE field_id IN ('A18', 'A24', 'A25', 'A26')"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET show_in_appendix = true WHERE field_id IN ('A15', 'A16')"
        )
    )
    op.execute(sa.text("UPDATE master_fields SET is_required = true WHERE field_id = 'C08'"))
    op.execute(
        sa.text("UPDATE master_fields SET appendix_clause_ref = '4.3(a)' WHERE field_id = 'A17'")
    )
    op.execute(
        sa.text(
            "UPDATE master_fields SET appendix_clause_ref = '4.3(b)' "
            "WHERE field_id IN ('A18', 'A24', 'A25', 'A26')"
        )
    )
