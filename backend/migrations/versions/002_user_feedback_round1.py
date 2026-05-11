"""user-feedback round 1: C05-C07 free-text, C14 security type, resolution original_clause_text

Revision ID: 002_user_feedback_round1
Revises: 001_initial
Create Date: 2026-05-11 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "002_user_feedback_round1"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. comments_resolution_sheets gains original_clause_text so admin can
    #    paste the verbatim SCA clause being commented on, for side-by-side
    #    display next to subcontractor_comment in the Resolution UI.
    op.add_column(
        "comments_resolution_sheets",
        sa.Column("original_clause_text", sa.Text(), nullable=True),
    )

    # 2. C05/C06/C07 input_type number -> text. Admin needs to enter values
    #    like "60 days PDC" or "30 days from completion", not just integers.
    op.execute(
        "UPDATE master_fields SET input_type = 'text' "
        "WHERE field_id IN ('C05', 'C06', 'C07')"
    )

    # 3. Insert C14 (Performance Security Type) into every conditions master
    #    template that is missing it. Idempotent via NOT EXISTS guard so this
    #    is safe to re-run after templates get versioned.
    op.execute(
        """
        INSERT INTO master_fields
            (id, template_id, field_id, clause_number, field_label, input_type,
             default_value, is_required, auto_source_field_id,
             appendix_row_label, appendix_clause_ref, show_in_appendix, sort_order)
        SELECT
            gen_random_uuid(), mt.id, 'C14', '3.4.2',
            'Performance Security Type', 'dropdown',
            NULL, true, NULL,
            'Performance Security Type', '3.4.2', true, 14
        FROM master_templates mt
        WHERE mt.type = 'conditions'
          AND NOT EXISTS (
              SELECT 1 FROM master_fields mf
              WHERE mf.template_id = mt.id AND mf.field_id = 'C14'
          )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM master_fields WHERE field_id = 'C14'")
    op.execute(
        "UPDATE master_fields SET input_type = 'number' "
        "WHERE field_id IN ('C05', 'C06', 'C07')"
    )
    op.drop_column("comments_resolution_sheets", "original_clause_text")
