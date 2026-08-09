"""Rename A17 field_label to 'Time for Completion - Subcontract Works in days'.

Revision ID: 022_a17_label_in_days
Revises: 021_show_a15_again
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "022_a17_label_in_days"
down_revision: str | None = "021_show_a15_again"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET field_label = 'Time for Completion - Subcontract Works in days' "
            "WHERE field_id = 'A17'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET field_label = 'Time for Completion - Subcontract Works' "
            "WHERE field_id = 'A17'"
        )
    )
