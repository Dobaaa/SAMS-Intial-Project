"""Add C15 "Optional Terms" free-text clause to conditions templates.

BGCC asked for a new paragraph-input clause C15 "Optional Terms" that renders
as the last row of the Appendix continuation table on page 7 (the {{C15}}
token added to the master docx by scripts/apply_master_c15_patch.py). This
migration inserts the matching field-catalog row into every conditions master
template that doesn't already have it. Idempotent via a NOT EXISTS guard,
mirroring how migration 002 added C14.

Revision ID: 006_add_c15_optional_terms
Revises: 005_security_cheque_label
Create Date: 2026-05-20
"""

from collections.abc import Sequence

from alembic import op


revision: str = "006_add_c15_optional_terms"
down_revision: str | None = "005_security_cheque_label"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO master_fields
            (id, template_id, field_id, clause_number, field_label, input_type,
             default_value, is_required, auto_source_field_id,
             appendix_row_label, appendix_clause_ref, show_in_appendix, sort_order)
        SELECT
            gen_random_uuid(), mt.id, 'C15', '',
            'Optional Terms', 'textarea',
            NULL, false, NULL,
            'Optional Terms', NULL, true, 15
        FROM master_templates mt
        WHERE mt.type = 'conditions'
          AND NOT EXISTS (
              SELECT 1 FROM master_fields mf
              WHERE mf.template_id = mt.id AND mf.field_id = 'C15'
          )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM master_fields WHERE field_id = 'C15'")
