"""Rename C02/A08 field_label from 'Subcontract Quantities Type' to 'Contract Type'.

Revision ID: 017_rename_c02
Revises: 016_appendix_polish
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "017_rename_c02"
down_revision: str | None = "016_appendix_polish"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET field_label = 'Contract Type' "
            "WHERE field_id IN ('C02', 'A08')"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET field_label = 'Subcontract Quantities Type' "
            "WHERE field_id IN ('C02', 'A08')"
        )
    )
