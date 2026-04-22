import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from middleware.rbac import get_current_user
from models.user import User
from models.workflow import WorkflowStep
from services.workflow_engine import (
    approve_step,
    get_pending_for_role,
    get_workflow_agreement_summary,
    return_step,
)

router = APIRouter(prefix="/workflow", tags=["workflow"])


class ReturnPayload(BaseModel):
    comment_text: str
    clause_reference: str | None = None


@router.get("/pending")
async def get_pending_workflows(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return await get_pending_for_role(db, current_user.role)


@router.post("/{step_id}/approve")
async def approve_workflow_step(
    step_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    step_res = await db.execute(select(WorkflowStep).where(WorkflowStep.id == step_id))
    step = step_res.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow step not found")
    if step.role_required != current_user.role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed for this role")
    await approve_step(db, step, current_user)
    return {"status": "approved"}


@router.post("/{step_id}/return")
async def return_workflow_step(
    step_id: uuid.UUID,
    payload: ReturnPayload,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    step_res = await db.execute(select(WorkflowStep).where(WorkflowStep.id == step_id))
    step = step_res.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow step not found")
    if step.role_required != current_user.role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed for this role")

    try:
        comment = await return_step(db, step, current_user, payload.comment_text, payload.clause_reference)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "returned", "comment_id": str(comment.id)}


@router.get("/agreements/{agreement_id}")
async def get_workflow_agreement(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> dict:
    data = await get_workflow_agreement_summary(db, str(agreement_id))
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")
    return data
