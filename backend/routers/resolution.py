import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from middleware.rbac import get_current_user, require_role
from models.agreement import Agreement
from models.resolution import CommentsResolutionSheet
from models.user import RoleEnum, User
from services.resolution_service import (
    create_resolution_sheet,
    get_resolution_rows,
    submit_resolution_for_approval,
    update_resolution_item,
)

router = APIRouter(prefix="/resolution", tags=["resolution"])


class ResolutionItemCreate(BaseModel):
    subcontractor_comment: str
    clause_reference: str | None = None
    original_clause_text: str | None = None


class ResolutionSheetCreatePayload(BaseModel):
    items: list[ResolutionItemCreate]


class ResolutionItemUpdatePayload(BaseModel):
    original_clause_text: str | None = None
    ai_suggested_response: str | None = None
    pd_response: str | None = None
    om_response: str | None = None
    final_response: str | None = None
    is_resolved: bool | None = None


@router.get("/{agreement_id}")
async def get_resolution(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> list[dict]:
    rows = await get_resolution_rows(db, agreement_id)
    return [
        {
            "id": str(row.id),
            "agreement_id": str(row.agreement_id),
            "subcontractor_comment": row.subcontractor_comment,
            "clause_reference": row.clause_reference,
            "original_clause_text": row.original_clause_text,
            "ai_suggested_response": row.ai_suggested_response,
            "pd_response": row.pd_response,
            "om_response": row.om_response,
            "final_response": row.final_response,
            "is_resolved": row.is_resolved,
            "last_edited_by": str(row.last_edited_by) if row.last_edited_by else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    ]


@router.put("/{agreement_id}/items/{item_id}")
async def update_resolution_row(
    agreement_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ResolutionItemUpdatePayload,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    if current_user.role not in {RoleEnum.admin, RoleEnum.project_director, RoleEnum.operation_manager}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    result = await db.execute(
        select(CommentsResolutionSheet).where(
            CommentsResolutionSheet.id == item_id,
            CommentsResolutionSheet.agreement_id == agreement_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resolution item not found")

    updated = await update_resolution_item(db, row, current_user, payload.model_dump(exclude_unset=True))
    return {
        "status": "success",
        "data": {
            "id": str(updated.id),
            "original_clause_text": updated.original_clause_text,
            "ai_suggested_response": updated.ai_suggested_response,
            "pd_response": updated.pd_response,
            "om_response": updated.om_response,
            "final_response": updated.final_response,
            "is_resolved": updated.is_resolved,
        },
    }


@router.post("/{agreement_id}/submit-for-approval", dependencies=[Depends(require_role(RoleEnum.admin))])
async def resolution_submit_for_approval(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    agreement_result = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    agreement = agreement_result.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")
    await submit_resolution_for_approval(db, agreement)
    return {"status": "submitted"}
