"""Re-show A15 (Commencement Date) in appendix — reverses 020_hide_a15.

Migration 020 hid A15 as part of an over-broad interpretation of BGCC req 3
("no longer required") that deleted the field entirely. Corrected: A15 stays
in the appendix, already optional (is_required=False, unchanged), and the
Appendix Builder shows clause 4.1's own definition text as fallback content
when left blank (implemented in pdf_service.generate_agreement_pdf, not the
schema — no field/schema change needed for the fallback itself).

Revision ID: 021_show_a15_again
Revises: 020_hide_a15
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "021_show_a15_again"
down_revision: str | None = "020_hide_a15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET show_in_appendix = true "
            "WHERE field_id = 'A15'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET show_in_appendix = false "
            "WHERE field_id = 'A15'"
        )
    )
