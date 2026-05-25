"""Rename A21 field_label from 'Maximum Liquidated Damages (%)' to 'Maximum Liquidated Damages in AED'.

Revision ID: 012_rename_a21_label
Revises: 011_max_ld_display
Create Date: 2026-05-25
"""

import sqlalchemy as sa
from alembic import op

revision: str = "012_rename_a21_label"
down_revision: str | None = "011_max_ld_display"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "UPDATE master_fields SET field_label = 'Maximum Liquidated Damages in AED' "
        "WHERE field_id = 'A21'"
    ))


def downgrade() -> None:
    op.execute(sa.text(
        "UPDATE master_fields SET field_label = 'Maximum Liquidated Damages (%)' "
        "WHERE field_id = 'A21'"
    ))
