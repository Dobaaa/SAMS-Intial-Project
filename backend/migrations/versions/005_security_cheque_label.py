"""Rename C14 Performance Security Type option to "Company Security Cheque".

The dropdown alternative "Company Undated Security Cheque" was shortened to
"Company Security Cheque" per BGCC. The option list is hard-coded in the
frontend, so already-saved agreements still carry the old literal in
agreement_field_values.entered_value. This migration rewrites those rows so
existing agreements re-render with the new label (PDFs regenerate from data).

Revision ID: 005_rename_security_cheque_option
Revises: 004_clause_revisions
Create Date: 2026-05-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "005_security_cheque_label"
down_revision: str | None = "004_clause_revisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = "Company Undated Security Cheque"
_NEW = "Company Security Cheque"


_STMT = sa.text(
    """
    UPDATE agreement_field_values
    SET entered_value = :new
    WHERE field_id = 'C14' AND entered_value = :old
    """
)


def upgrade() -> None:
    op.get_bind().execute(_STMT, {"new": _NEW, "old": _OLD})


def downgrade() -> None:
    op.get_bind().execute(_STMT, {"new": _OLD, "old": _NEW})
