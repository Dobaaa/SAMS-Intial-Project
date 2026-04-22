"""initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-04-21 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


role_enum = sa.Enum("admin", "project_director", "accounts", "operation_manager", "gm", name="role_enum")
template_type_enum = sa.Enum("form", "conditions", "appendix", name="template_type_enum")
input_type_enum = sa.Enum("text", "number", "date", "dropdown", "textarea", "multifield", "table", name="input_type_enum")
agreement_status_enum = sa.Enum(
    "under_drafting",
    "under_internal_review",
    "draft_forwarded_to_subcontractor",
    "under_subcontractor_review",
    "under_subcontractor_signature",
    "under_bgcc_revision",
    "under_gm_signature",
    "completed",
    name="agreement_status_enum",
)
workflow_step_status_enum = sa.Enum("pending", "approved", "returned", "skipped", name="workflow_step_status_enum")
comment_status_enum = sa.Enum("open", "in_discussion", "resolved", name="comment_status_enum")
review_type_enum = sa.Enum("comparison", "risk", "summary", "response_suggestion", "validation", name="review_type_enum")
pdf_type_enum = sa.Enum("draft", "final", "executed", name="pdf_type_enum")


def upgrade() -> None:
    bind = op.get_bind()
    role_enum.create(bind, checkfirst=True)
    template_type_enum.create(bind, checkfirst=True)
    input_type_enum.create(bind, checkfirst=True)
    agreement_status_enum.create(bind, checkfirst=True)
    workflow_step_status_enum.create(bind, checkfirst=True)
    comment_status_enum.create(bind, checkfirst=True)
    review_type_enum.create(bind, checkfirst=True)
    pdf_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", role_enum, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "master_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", template_type_enum, nullable=False),
        sa.Column("version_number", sa.String(length=50), nullable=False),
        sa.Column("version_date", sa.Date(), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_name", sa.String(length=255), nullable=False),
        sa.Column("project_code", sa.String(length=100), nullable=False),
        sa.Column("project_location", sa.String(length=255), nullable=True),
        sa.Column("employer_name", sa.String(length=255), nullable=True),
        sa.Column("engineer_name", sa.String(length=255), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_code"),
    )
    op.create_index("ix_projects_project_code", "projects", ["project_code"], unique=False)

    op.create_table(
        "subcontractors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("po_box", sa.String(length=100), nullable=True),
        sa.Column("trade_licence_no", sa.String(length=100), nullable=True),
        sa.Column("contact_person", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "agreements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reference_number", sa.String(length=120), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subcontractor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("form_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("conditions_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("appendix_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("current_status", agreement_status_enum, server_default=sa.text("'under_drafting'"), nullable=False),
        sa.Column("status_updated_on", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("gm_approval_date", sa.Date(), nullable=True),
        sa.Column("execution_date", sa.Date(), nullable=True),
        sa.Column("is_executed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["appendix_version_id"], ["master_templates.id"]),
        sa.ForeignKeyConstraint(["conditions_version_id"], ["master_templates.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["form_version_id"], ["master_templates.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["subcontractor_id"], ["subcontractors.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference_number"),
    )
    op.create_index("ix_agreements_reference_number", "agreements", ["reference_number"], unique=False)

    op.create_table(
        "master_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_id", sa.String(length=20), nullable=False),
        sa.Column("clause_number", sa.String(length=50), nullable=False),
        sa.Column("field_label", sa.String(length=255), nullable=False),
        sa.Column("input_type", input_type_enum, nullable=False),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.Column("is_required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("auto_source_field_id", sa.String(length=20), nullable=True),
        sa.Column("appendix_row_label", sa.String(length=255), nullable=True),
        sa.Column("appendix_clause_ref", sa.String(length=50), nullable=True),
        sa.Column("show_in_appendix", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["master_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_master_fields_field_id", "master_fields", ["field_id"], unique=False)
    op.create_index("ix_master_fields_template_id", "master_fields", ["template_id"], unique=False)

    op.create_table(
        "agreement_field_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_id", sa.String(length=20), nullable=False),
        sa.Column("entered_value", sa.Text(), nullable=True),
        sa.Column("is_modified_from_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("modification_reason", sa.Text(), nullable=True),
        sa.Column("entered_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entered_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agreement_field_values_agreement_id", "agreement_field_values", ["agreement_id"], unique=False)
    op.create_index("ix_agreement_field_values_field_id", "agreement_field_values", ["field_id"], unique=False)

    op.create_table(
        "appendix_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_id", sa.String(length=20), nullable=False),
        sa.Column("show_in_appendix", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("admin_extra_note", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_modified_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["last_modified_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appendix_config_agreement_id", "appendix_config", ["agreement_id"], unique=False)
    op.create_index("ix_appendix_config_field_id", "appendix_config", ["field_id"], unique=False)

    op.create_table(
        "workflow_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_name", sa.String(length=100), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("role_required", role_enum, nullable=False),
        sa.Column("status", workflow_step_status_enum, server_default=sa.text("'pending'"), nullable=False),
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("acted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["acted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_steps_agreement_id", "workflow_steps", ["agreement_id"], unique=False)

    op.create_table(
        "workflow_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_step_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_edited_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("comment_text", sa.Text(), nullable=False),
        sa.Column("clause_reference", sa.String(length=100), nullable=True),
        sa.Column("status", comment_status_enum, server_default=sa.text("'open'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["last_edited_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["original_author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["workflow_step_id"], ["workflow_steps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_comments_agreement_id", "workflow_comments", ["agreement_id"], unique=False)
    op.create_index("ix_workflow_comments_workflow_step_id", "workflow_comments", ["workflow_step_id"], unique=False)

    op.create_table(
        "comment_edit_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("comment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("edited_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_text", sa.Text(), nullable=False),
        sa.Column("new_text", sa.Text(), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["comment_id"], ["workflow_comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["edited_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comment_edit_history_comment_id", "comment_edit_history", ["comment_id"], unique=False)

    op.create_table(
        "comments_resolution_sheets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subcontractor_comment", sa.Text(), nullable=False),
        sa.Column("clause_reference", sa.String(length=100), nullable=True),
        sa.Column("ai_suggested_response", sa.Text(), nullable=True),
        sa.Column("pd_response", sa.Text(), nullable=True),
        sa.Column("om_response", sa.Text(), nullable=True),
        sa.Column("final_response", sa.Text(), nullable=True),
        sa.Column("last_edited_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["last_edited_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comments_resolution_sheets_agreement_id", "comments_resolution_sheets", ["agreement_id"], unique=False)

    op.create_table(
        "ai_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_step_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_type", review_type_enum, nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("findings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_step_id"], ["workflow_steps.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_reviews_agreement_id", "ai_reviews", ["agreement_id"], unique=False)
    op.create_index("ix_ai_reviews_workflow_step_id", "ai_reviews", ["workflow_step_id"], unique=False)

    op.create_table(
        "deviation_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("report_data_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deviation_reports_agreement_id", "deviation_reports", ["agreement_id"], unique=False)

    op.create_table(
        "pdf_outputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pdf_type", pdf_type_enum, nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("generated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("watermark_type", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pdf_outputs_agreement_id", "pdf_outputs", ["agreement_id"], unique=False)

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("old_value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_action", "audit_log", ["action"], unique=False)
    op.create_index("ix_audit_log_entity_id", "audit_log", ["entity_id"], unique=False)
    op.create_index("ix_audit_log_entity_type", "audit_log", ["entity_type"], unique=False)
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_log_user_id", table_name="audit_log")
    op.drop_index("ix_audit_log_entity_type", table_name="audit_log")
    op.drop_index("ix_audit_log_entity_id", table_name="audit_log")
    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("ix_pdf_outputs_agreement_id", table_name="pdf_outputs")
    op.drop_table("pdf_outputs")

    op.drop_index("ix_deviation_reports_agreement_id", table_name="deviation_reports")
    op.drop_table("deviation_reports")

    op.drop_index("ix_ai_reviews_workflow_step_id", table_name="ai_reviews")
    op.drop_index("ix_ai_reviews_agreement_id", table_name="ai_reviews")
    op.drop_table("ai_reviews")

    op.drop_index("ix_comments_resolution_sheets_agreement_id", table_name="comments_resolution_sheets")
    op.drop_table("comments_resolution_sheets")

    op.drop_index("ix_comment_edit_history_comment_id", table_name="comment_edit_history")
    op.drop_table("comment_edit_history")

    op.drop_index("ix_workflow_comments_workflow_step_id", table_name="workflow_comments")
    op.drop_index("ix_workflow_comments_agreement_id", table_name="workflow_comments")
    op.drop_table("workflow_comments")

    op.drop_index("ix_workflow_steps_agreement_id", table_name="workflow_steps")
    op.drop_table("workflow_steps")

    op.drop_index("ix_appendix_config_field_id", table_name="appendix_config")
    op.drop_index("ix_appendix_config_agreement_id", table_name="appendix_config")
    op.drop_table("appendix_config")

    op.drop_index("ix_agreement_field_values_field_id", table_name="agreement_field_values")
    op.drop_index("ix_agreement_field_values_agreement_id", table_name="agreement_field_values")
    op.drop_table("agreement_field_values")

    op.drop_index("ix_master_fields_template_id", table_name="master_fields")
    op.drop_index("ix_master_fields_field_id", table_name="master_fields")
    op.drop_table("master_fields")

    op.drop_index("ix_agreements_reference_number", table_name="agreements")
    op.drop_table("agreements")

    op.drop_table("subcontractors")

    op.drop_index("ix_projects_project_code", table_name="projects")
    op.drop_table("projects")

    op.drop_table("master_templates")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    pdf_type_enum.drop(bind, checkfirst=True)
    review_type_enum.drop(bind, checkfirst=True)
    comment_status_enum.drop(bind, checkfirst=True)
    workflow_step_status_enum.drop(bind, checkfirst=True)
    agreement_status_enum.drop(bind, checkfirst=True)
    input_type_enum.drop(bind, checkfirst=True)
    template_type_enum.drop(bind, checkfirst=True)
    role_enum.drop(bind, checkfirst=True)
