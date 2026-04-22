import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db_session
from middleware.rbac import get_current_user
from models.user import RoleEnum, User
from models.workflow import CommentEditHistory, CommentStatusEnum, WorkflowComment
from services.email_service import send_email

router = APIRouter(tags=["comments"])


class CommentUpdatePayload(BaseModel):
    comment_text: str


class CommentStatusPayload(BaseModel):
    status: CommentStatusEnum


def _history_to_dict(item: CommentEditHistory) -> dict:
    return {
        "id": str(item.id),
        "edited_by": str(item.edited_by),
        "edited_by_name": item.edited_by_user.name if item.edited_by_user else None,
        "previous_text": item.previous_text,
        "new_text": item.new_text,
        "edited_at": item.edited_at.isoformat() if item.edited_at else None,
    }


def _comment_to_dict(item: WorkflowComment) -> dict:
    return {
        "id": str(item.id),
        "workflow_step_id": str(item.workflow_step_id),
        "agreement_id": str(item.agreement_id),
        "original_author_id": str(item.original_author_id),
        "original_author_name": item.original_author.name if item.original_author else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "comment_text": item.comment_text,
        "clause_reference": item.clause_reference,
        "status": item.status.value,
        "last_edited_by_id": str(item.last_edited_by_id) if item.last_edited_by_id else None,
        "last_edited_by_name": item.last_edited_by_user.name if item.last_edited_by_user else None,
        "last_edited_at": item.last_edited_at.isoformat() if item.last_edited_at else None,
        "edit_history": [_history_to_dict(h) for h in sorted(item.edit_history, key=lambda x: x.edited_at)],
    }


@router.get("/agreements/{agreement_id}/comments")
async def get_agreement_comments(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> list[dict]:
    result = await db.execute(
        select(WorkflowComment)
        .where(WorkflowComment.agreement_id == agreement_id)
        .options(
            selectinload(WorkflowComment.original_author),
            selectinload(WorkflowComment.last_edited_by_user),
            selectinload(WorkflowComment.edit_history).selectinload(CommentEditHistory.edited_by_user),
        )
        .order_by(WorkflowComment.created_at.asc())
    )
    comments = result.scalars().all()
    return [_comment_to_dict(comment) for comment in comments]


@router.put("/comments/{comment_id}")
async def edit_comment(
    comment_id: uuid.UUID,
    payload: CommentUpdatePayload,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    if not payload.comment_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="comment_text cannot be empty")

    result = await db.execute(
        select(WorkflowComment)
        .where(WorkflowComment.id == comment_id)
        .options(
            selectinload(WorkflowComment.original_author),
            selectinload(WorkflowComment.last_edited_by_user),
            selectinload(WorkflowComment.edit_history).selectinload(CommentEditHistory.edited_by_user),
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    previous_text = comment.comment_text
    new_text = payload.comment_text.strip()
    if previous_text == new_text:
        return _comment_to_dict(comment)

    edit = CommentEditHistory(
        comment_id=comment.id,
        edited_by=current_user.id,
        previous_text=previous_text,
        new_text=new_text,
    )
    db.add(edit)

    comment.comment_text = new_text
    comment.last_edited_by_id = current_user.id
    comment.last_edited_at = datetime.now(UTC)
    await db.commit()

    # Notify original author that the comment was edited.
    if comment.original_author and comment.original_author.email:
        await send_email(
            to_email=comment.original_author.email,
            subject="SAMS Comment Updated",
            body=(
                f"Your comment has been edited.\n"
                f"Edited by: {current_user.name}\n"
                f"Previous text: {previous_text}\n"
                f"New text: {new_text}"
            ),
        )

    refreshed = await db.execute(
        select(WorkflowComment)
        .where(WorkflowComment.id == comment_id)
        .options(
            selectinload(WorkflowComment.original_author),
            selectinload(WorkflowComment.last_edited_by_user),
            selectinload(WorkflowComment.edit_history).selectinload(CommentEditHistory.edited_by_user),
        )
    )
    return _comment_to_dict(refreshed.scalar_one())


@router.patch("/comments/{comment_id}/status")
async def update_comment_status(
    comment_id: uuid.UUID,
    payload: CommentStatusPayload,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(WorkflowComment)
        .where(WorkflowComment.id == comment_id)
        .options(
            selectinload(WorkflowComment.original_author),
            selectinload(WorkflowComment.last_edited_by_user),
            selectinload(WorkflowComment.edit_history).selectinload(CommentEditHistory.edited_by_user),
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    if payload.status == CommentStatusEnum.resolved and current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Admin can mark comments as resolved")

    comment.status = payload.status
    comment.last_edited_by_id = current_user.id
    comment.last_edited_at = datetime.now(UTC)
    await db.commit()

    refreshed = await db.execute(
        select(WorkflowComment)
        .where(WorkflowComment.id == comment_id)
        .options(
            selectinload(WorkflowComment.original_author),
            selectinload(WorkflowComment.last_edited_by_user),
            selectinload(WorkflowComment.edit_history).selectinload(CommentEditHistory.edited_by_user),
        )
    )
    return _comment_to_dict(refreshed.scalar_one())
