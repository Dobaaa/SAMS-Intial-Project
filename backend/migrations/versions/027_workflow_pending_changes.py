"""Add pending_changes to workflow_steps (2026-09-05 client feedback: an
already-approved reviewer must only need to re-review the specific points
Admin changed, not the whole agreement again).

Revision ID: 027_workflow_pending_changes
Revises: 026_agreement_field_reviews
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "027_workflow_pending_changes"
down_revision: str | None = "026_agreement_field_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workflow_steps", sa.Column("pending_changes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("workflow_steps", "pending_changes")
