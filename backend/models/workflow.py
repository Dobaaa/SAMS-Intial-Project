import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base
from models.user import RoleEnum


class WorkflowStepStatusEnum(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    returned = "returned"
    skipped = "skipped"


class CommentStatusEnum(str, enum.Enum):
    open = "open"
    in_discussion = "in_discussion"
    resolved = "resolved"


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agreements.id", ondelete="CASCADE"), nullable=False, index=True)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    role_required: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum, name="role_enum"), nullable=False)
    status: Mapped[WorkflowStepStatusEnum] = mapped_column(
        Enum(WorkflowStepStatusEnum, name="workflow_step_status_enum"),
        nullable=False,
        default=WorkflowStepStatusEnum.pending,
        server_default=WorkflowStepStatusEnum.pending.value,
    )
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    acted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # Comma-joined field IDs (or "CLAUSE") changed by Admin since this step was
    # approved. Populated by notify_already_approved_reviewers, cleared by
    # reaffirm_step — lets an already-approved reviewer re-check only the
    # specific points that changed instead of the whole agreement again.
    pending_changes: Mapped[str | None] = mapped_column(Text, nullable=True)

    agreement = relationship("Agreement", back_populates="workflow_steps")
    assigned_user = relationship("User", back_populates="assigned_workflow_steps", foreign_keys=[assigned_user_id])
    acted_by_user = relationship("User", back_populates="acted_workflow_steps", foreign_keys=[acted_by])
    comments = relationship("WorkflowComment", back_populates="workflow_step", cascade="all, delete-orphan")


class WorkflowComment(Base):
    __tablename__ = "workflow_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_step_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False, index=True)
    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agreements.id", ondelete="CASCADE"), nullable=False, index=True)
    original_author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    last_edited_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    clause_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[CommentStatusEnum] = mapped_column(
        Enum(CommentStatusEnum, name="comment_status_enum"),
        nullable=False,
        default=CommentStatusEnum.open,
        server_default=CommentStatusEnum.open.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workflow_step = relationship("WorkflowStep", back_populates="comments")
    agreement = relationship("Agreement", back_populates="workflow_comments")
    original_author = relationship("User", back_populates="authored_comments", foreign_keys=[original_author_id])
    last_edited_by_user = relationship("User", back_populates="edited_comments", foreign_keys=[last_edited_by_id])
    edit_history = relationship("CommentEditHistory", back_populates="comment", cascade="all, delete-orphan")
    reactions = relationship("CommentReaction", back_populates="comment", cascade="all, delete-orphan")


class CommentReaction(Base):
    __tablename__ = "comment_reactions"
    __table_args__ = (UniqueConstraint("comment_id", "reactor_user_id", name="uq_comment_reaction_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_comments.id", ondelete="CASCADE"), nullable=False, index=True)
    reactor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reactor_role: Mapped[str] = mapped_column(String(50), nullable=False)
    reaction: Mapped[str] = mapped_column(String(20), nullable=False)  # "accepted" | "rejected"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    comment = relationship("WorkflowComment", back_populates="reactions")
    reactor = relationship("User", foreign_keys=[reactor_user_id])


class CommentEditHistory(Base):
    __tablename__ = "comment_edit_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_comments.id", ondelete="CASCADE"), nullable=False, index=True)
    edited_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    previous_text: Mapped[str] = mapped_column(Text, nullable=False)
    new_text: Mapped[str] = mapped_column(Text, nullable=False)
    edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    comment = relationship("WorkflowComment", back_populates="edit_history")
    edited_by_user = relationship("User", back_populates="comment_edits", foreign_keys=[edited_by])
