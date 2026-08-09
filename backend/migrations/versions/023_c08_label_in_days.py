"""Rename C08 field_label to 'Time for Completion (Project) in days'.

Revision ID: 023_c08_label_in_days
Revises: 022_a17_label_in_days
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "023_c08_label_in_days"
down_revision: str | None = "022_a17_label_in_days"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET field_label = 'Time for Completion (Project) in days' "
            "WHERE field_id = 'C08'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE master_fields SET field_label = 'Time for Completion (Project)' "
            "WHERE field_id = 'C08'"
        )
    )
