"""Add quality_surveyor, estimator, project_manager roles + project_users table.

Revision ID: 008_new_roles_and_project_users
Revises: 007_predefined_projects
Create Date: 2026-05-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "008_new_roles_and_project_users"
down_revision: str | None = "007_predefined_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new enum values (PostgreSQL 9.3+ supports IF NOT EXISTS)
    op.execute("ALTER TYPE role_enum ADD VALUE IF NOT EXISTS 'quality_surveyor'")
    op.execute("ALTER TYPE role_enum ADD VALUE IF NOT EXISTS 'estimator'")
    op.execute("ALTER TYPE role_enum ADD VALUE IF NOT EXISTS 'project_manager'")

    op.create_table(
        "project_users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_users"),
    )
    op.create_index("ix_project_users_project_id", "project_users", ["project_id"])
    op.create_index("ix_project_users_user_id", "project_users", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_project_users_user_id", table_name="project_users")
    op.drop_index("ix_project_users_project_id", table_name="project_users")
    op.drop_table("project_users")
    # PostgreSQL does not support DROP VALUE from enums; downgrade leaves the values in place.
