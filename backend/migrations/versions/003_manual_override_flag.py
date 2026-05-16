"""Add is_manual_override to agreement_field_values (Rev 01 item 35).

A-fields with auto_source_field_id now ALWAYS re-derive from their source
unless an admin explicitly opts into override via the AppendixBuilder Edit
flow. This flag distinguishes "still auto-following the source" from "admin
locked this value, don't clobber on cascade".

Revision ID: 003_manual_override_flag
Revises: 002_user_feedback_round1
Create Date: 2026-05-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "003_manual_override_flag"
down_revision: str | None = "002_user_feedback_round1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agreement_field_values",
        sa.Column(
            "is_manual_override",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("agreement_field_values", "is_manual_override")
