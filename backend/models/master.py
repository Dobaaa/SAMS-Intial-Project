import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class TemplateTypeEnum(str, enum.Enum):
    form = "form"
    conditions = "conditions"
    appendix = "appendix"


class InputTypeEnum(str, enum.Enum):
    text = "text"
    number = "number"
    date = "date"
    dropdown = "dropdown"
    textarea = "textarea"
    multifield = "multifield"
    table = "table"


class MasterTemplate(Base):
    __tablename__ = "master_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[TemplateTypeEnum] = mapped_column(Enum(TemplateTypeEnum, name="template_type_enum"), nullable=False)
    version_number: Mapped[str] = mapped_column(String(50), nullable=False)
    version_date: Mapped[date] = mapped_column(Date, nullable=False)
    content_html: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    created_by_user = relationship("User", back_populates="created_templates", foreign_keys=[created_by])
    fields = relationship("MasterField", back_populates="template", cascade="all, delete-orphan")


class MasterField(Base):
    __tablename__ = "master_fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("master_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    field_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    clause_number: Mapped[str] = mapped_column(String(50), nullable=False)
    field_label: Mapped[str] = mapped_column(String(255), nullable=False)
    input_type: Mapped[InputTypeEnum] = mapped_column(Enum(InputTypeEnum, name="input_type_enum"), nullable=False)
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    auto_source_field_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    appendix_row_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    appendix_clause_ref: Mapped[str | None] = mapped_column(String(50), nullable=True)
    show_in_appendix: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    template = relationship("MasterTemplate", back_populates="fields")
