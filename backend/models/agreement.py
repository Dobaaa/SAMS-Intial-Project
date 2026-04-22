import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, event, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class AgreementStatusEnum(str, enum.Enum):
    under_drafting = "under_drafting"
    under_internal_review = "under_internal_review"
    draft_forwarded_to_subcontractor = "draft_forwarded_to_subcontractor"
    under_subcontractor_review = "under_subcontractor_review"
    under_subcontractor_signature = "under_subcontractor_signature"
    under_bgcc_revision = "under_bgcc_revision"
    under_gm_signature = "under_gm_signature"
    completed = "completed"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    project_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    engineer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    agreements = relationship("Agreement", back_populates="project")


class Subcontractor(Base):
    __tablename__ = "subcontractors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    po_box: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trade_licence_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    agreements = relationship("Agreement", back_populates="subcontractor")


class Agreement(Base):
    __tablename__ = "agreements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference_number: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    subcontractor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subcontractors.id"), nullable=False)
    form_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("master_templates.id"), nullable=True)
    conditions_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("master_templates.id"), nullable=True)
    appendix_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("master_templates.id"), nullable=True)
    current_status: Mapped[AgreementStatusEnum] = mapped_column(
        Enum(AgreementStatusEnum, name="agreement_status_enum"),
        nullable=False,
        default=AgreementStatusEnum.under_drafting,
        server_default=AgreementStatusEnum.under_drafting.value,
    )
    status_updated_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    gm_approval_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    execution_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="agreements")
    subcontractor = relationship("Subcontractor", back_populates="agreements")
    created_by_user = relationship("User", back_populates="created_agreements", foreign_keys=[created_by])
    field_values = relationship("AgreementFieldValue", back_populates="agreement", cascade="all, delete-orphan")
    appendix_rows = relationship("AppendixConfig", back_populates="agreement", cascade="all, delete-orphan")
    workflow_steps = relationship("WorkflowStep", back_populates="agreement", cascade="all, delete-orphan")
    workflow_comments = relationship("WorkflowComment", back_populates="agreement", cascade="all, delete-orphan")
    resolution_items = relationship("CommentsResolutionSheet", back_populates="agreement", cascade="all, delete-orphan")
    ai_reviews = relationship("AIReview", back_populates="agreement", cascade="all, delete-orphan")
    deviation_reports = relationship("DeviationReport", back_populates="agreement", cascade="all, delete-orphan")
    pdf_outputs = relationship("PDFOutput", back_populates="agreement", cascade="all, delete-orphan")


class AgreementFieldValue(Base):
    __tablename__ = "agreement_field_values"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agreements.id", ondelete="CASCADE"), nullable=False, index=True)
    field_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    entered_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_modified_from_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    modification_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    entered_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    agreement = relationship("Agreement", back_populates="field_values")
    entered_by_user = relationship("User", back_populates="entered_field_values", foreign_keys=[entered_by])


class AppendixConfig(Base):
    __tablename__ = "appendix_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agreements.id", ondelete="CASCADE"), nullable=False, index=True)
    field_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    show_in_appendix: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    admin_extra_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_modified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    last_modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    agreement = relationship("Agreement", back_populates="appendix_rows")
    last_modified_by_user = relationship("User", back_populates="modified_appendix_rows", foreign_keys=[last_modified_by])


@event.listens_for(Agreement.current_status, "set", retval=False)
def _on_status_change(target: Agreement, value: AgreementStatusEnum, oldvalue: AgreementStatusEnum, initiator):  # type: ignore[no-untyped-def]
    if oldvalue != value:
        target.status_updated_on = datetime.now()
