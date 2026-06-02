import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class ReviewTypeEnum(str, enum.Enum):
    comparison = "comparison"
    risk = "risk"
    summary = "summary"
    response_suggestion = "response_suggestion"
    validation = "validation"
    grammar = "grammar"


class PDFTypeEnum(str, enum.Enum):
    draft = "draft"
    final = "final"
    executed = "executed"


class AIReview(Base):
    __tablename__ = "ai_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agreements.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_steps.id"), nullable=True, index=True)
    review_type: Mapped[ReviewTypeEnum] = mapped_column(Enum(ReviewTypeEnum, name="review_type_enum"), nullable=False)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    findings_json: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)

    agreement = relationship("Agreement", back_populates="ai_reviews")


class DeviationReport(Base):
    __tablename__ = "deviation_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agreements.id", ondelete="CASCADE"), nullable=False, index=True)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    report_data_json: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    agreement = relationship("Agreement", back_populates="deviation_reports")
    generated_by_user = relationship("User", back_populates="generated_deviation_reports", foreign_keys=[generated_by])


class PDFOutput(Base):
    __tablename__ = "pdf_outputs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agreements.id", ondelete="CASCADE"), nullable=False, index=True)
    pdf_type: Mapped[PDFTypeEnum] = mapped_column(Enum(PDFTypeEnum, name="pdf_type_enum"), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    generated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    watermark_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    agreement = relationship("Agreement", back_populates="pdf_outputs")
    generated_by_user = relationship("User", back_populates="generated_pdf_outputs", foreign_keys=[generated_by])
