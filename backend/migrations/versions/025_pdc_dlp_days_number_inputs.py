"""C05/C06/C07/C10/A17/A19 input_type -> number (2026-08-26 client feedback
items 1/2/5); C10/A19 relabeled "...(months)" to guide the now-bare-number
entry, matching the existing A17/C08 "...in days" relabel precedent.

Revision ID: 025_pdc_dlp_days_number_inputs
Revises: 024_remove_commencement_date
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "025_pdc_dlp_days_number_inputs"
down_revision: str | None = "024_remove_commencement_date"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET input_type = 'number' "
            "WHERE field_id IN ('C05', 'C06', 'C07', 'C10', 'A17', 'A19')"
        )
    )
    op.execute(
        sa.text(
            "UPDATE master_fields SET field_label = 'Defects Liability Period (months)' "
            "WHERE field_id IN ('C10', 'A19')"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET input_type = 'text' "
            "WHERE field_id IN ('C05', 'C06', 'C07', 'C10', 'A17', 'A19')"
        )
    )
    op.execute(
        sa.text(
            "UPDATE master_fields SET field_label = 'Defects Liability Period' "
            "WHERE field_id IN ('C10', 'A19')"
        )
    )
