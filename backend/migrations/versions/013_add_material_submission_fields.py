"""Add A24/A25/A26 material-submission and shop-drawing milestone fields under 4.3(b).

BGCC requested three new appendix rows for the 4.3(b) Time for Completion
table on page 22 of the SCA agreement:
  - A24  Start of Material Submission
  - A25  Complete all Material Submission
  - A26  Start of Submission of Shop Drawings

These are text fields inserted immediately after the existing A18 (Milestones)
row in sort order. Existing A19-A23 sort_orders are shifted +3 to make room.

The matching {{A24}}/{{A25}}/{{A26}} tokens are added to the master docx by
running:  python backend/scripts/apply_master_4_3b_rows_patch.py

Revision ID: 013_add_material_submission_fields
Revises: 012_rename_a21_label
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013_material_fields"
down_revision: str | None = "012_rename_a21_label"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Shift A19-A23 sort_orders up by 3 to make room for A24/A25/A26 at 19/20/21.
    # Update in descending order to avoid transient uniqueness conflicts.
    for field_id, new_sort in [("A23", 26), ("A22", 25), ("A21", 24), ("A20", 23), ("A19", 22)]:
        op.execute(
            sa.text(
                "UPDATE master_fields SET sort_order = :so WHERE field_id = :fid"
            ).bindparams(so=new_sort, fid=field_id)
        )

    # Insert A24, A25, A26 into every appendix master template that doesn't
    # already have them (idempotent via NOT EXISTS guard).
    new_fields = [
        ("A24", "4.3(b)", "Start of Material Submission", "Start of Material Submission", 19),
        ("A25", "4.3(b)", "Complete all Material Submission", "Complete all Material Submission", 20),
        ("A26", "4.3(b)", "Start of Submission of Shop Drawings", "Start of Submission of Shop Drawings", 21),
    ]
    for field_id, clause_num, label, row_label, sort_order in new_fields:
        op.execute(
            sa.text(
                """
                INSERT INTO master_fields
                    (id, template_id, field_id, clause_number, field_label, input_type,
                     default_value, is_required, auto_source_field_id,
                     appendix_row_label, appendix_clause_ref, show_in_appendix, sort_order)
                SELECT
                    gen_random_uuid(), mt.id, :fid, :clause, :label, 'text',
                    NULL, false, NULL,
                    :row_label, :clause, true, :so
                FROM master_templates mt
                WHERE mt.type = 'appendix'
                  AND NOT EXISTS (
                      SELECT 1 FROM master_fields mf
                      WHERE mf.template_id = mt.id AND mf.field_id = :fid
                  )
                """
            ).bindparams(
                fid=field_id,
                clause=clause_num,
                label=label,
                row_label=row_label,
                so=sort_order,
            )
        )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM master_fields WHERE field_id IN ('A24', 'A25', 'A26')"))
    for field_id, orig_sort in [("A19", 19), ("A20", 20), ("A21", 21), ("A22", 22), ("A23", 23)]:
        op.execute(
            sa.text(
                "UPDATE master_fields SET sort_order = :so WHERE field_id = :fid"
            ).bindparams(so=orig_sort, fid=field_id)
        )
