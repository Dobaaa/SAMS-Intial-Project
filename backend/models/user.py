import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RoleEnum(str, enum.Enum):
    admin = "admin"
    project_director = "project_director"
    accounts = "accounts"
    operation_manager = "operation_manager"
    gm = "gm"
    quality_surveyor = "quality_surveyor"
    estimator = "estimator"
    project_manager = "project_manager"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum, name="role_enum"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_templates = relationship("MasterTemplate", back_populates="created_by_user", foreign_keys="MasterTemplate.created_by")
    created_agreements = relationship("Agreement", back_populates="created_by_user", foreign_keys="Agreement.created_by")
    entered_field_values = relationship("AgreementFieldValue", back_populates="entered_by_user", foreign_keys="AgreementFieldValue.entered_by")
    assigned_workflow_steps = relationship("WorkflowStep", back_populates="assigned_user", foreign_keys="WorkflowStep.assigned_user_id")
    acted_workflow_steps = relationship("WorkflowStep", back_populates="acted_by_user", foreign_keys="WorkflowStep.acted_by")
    authored_comments = relationship("WorkflowComment", back_populates="original_author", foreign_keys="WorkflowComment.original_author_id")
    edited_comments = relationship("WorkflowComment", back_populates="last_edited_by_user", foreign_keys="WorkflowComment.last_edited_by_id")
    comment_edits = relationship("CommentEditHistory", back_populates="edited_by_user", foreign_keys="CommentEditHistory.edited_by")
    modified_appendix_rows = relationship("AppendixConfig", back_populates="last_modified_by_user", foreign_keys="AppendixConfig.last_modified_by")
    resolution_edits = relationship("CommentsResolutionSheet", back_populates="last_edited_by_user", foreign_keys="CommentsResolutionSheet.last_edited_by")
    generated_deviation_reports = relationship("DeviationReport", back_populates="generated_by_user", foreign_keys="DeviationReport.generated_by")
    generated_pdf_outputs = relationship("PDFOutput", back_populates="generated_by_user", foreign_keys="PDFOutput.generated_by")
    audit_logs = relationship("AuditLog", back_populates="user", foreign_keys="AuditLog.user_id")
