import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from middleware.rbac import require_role
from models.agreement import Agreement
from models.user import RoleEnum, User
from services.agreement_service import create_draft_agreement, submit_for_review, update_agreement_fields
from services.resolution_service import create_resolution_sheet, record_subcontractor_response
from services.workflow_engine import resubmit_agreement

router = APIRouter(prefix="/agreements", tags=["agreements"])


class ProjectPayload(BaseModel):
    project_name: str
    project_code: str
    project_location: str | None = None
    employer_name: str | None = None
    engineer_name: str | None = None


class SubcontractorPayload(BaseModel):
    company_name: str
    po_box: str | None = None
    trade_licence_no: str | None = None
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None


class CreateAgreementPayload(BaseModel):
    project: ProjectPayload
    subcontractor: SubcontractorPayload
    reference_number: str | None = None


class UpdateFieldsPayload(BaseModel):
    values: dict[str, str]


class SubcontractorResponsePayload(BaseModel):
    response_type: str
    signed_scan_path: str | None = None
    comments_count: int | None = None


class ResolutionItemCreate(BaseModel):
    subcontractor_comment: str
    clause_reference: str | None = None


class ResolutionSheetCreatePayload(BaseModel):
    items: list[ResolutionItemCreate]


@router.post("/", dependencies=[Depends(require_role(RoleEnum.admin))])
async def create_agreement_draft(
    payload: CreateAgreementPayload,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(RoleEnum.admin)),
) -> dict:
    try:
        agreement = await create_draft_agreement(
            db=db,
            user=current_user,
            project_payload=payload.project.model_dump(),
            subcontractor_payload=payload.subcontractor.model_dump(),
            reference_number=payload.reference_number,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "id": str(agreement.id),
        "reference_number": agreement.reference_number,
        "status": agreement.current_status.value,
    }


@router.put("/{agreement_id}/fields", dependencies=[Depends(require_role(RoleEnum.admin))])
async def update_fields(
    agreement_id: uuid.UUID,
    payload: UpdateFieldsPayload,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(RoleEnum.admin)),
) -> dict:
    res = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    agreement = res.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")
    if agreement.is_executed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agreement is locked after execution")
    await update_agreement_fields(db, agreement, current_user, payload.values)
    return {"status": "success"}


@router.post("/{agreement_id}/submit", dependencies=[Depends(require_role(RoleEnum.admin))])
async def submit_agreement(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    res = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    agreement = res.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")
    await submit_for_review(db, agreement)
    return {"status": "submitted"}


@router.post("/{agreement_id}/resubmit", dependencies=[Depends(require_role(RoleEnum.admin))])
async def resubmit_returned_agreement(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    res = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    agreement = res.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")
    await resubmit_agreement(db, agreement)
    return {"status": "resubmitted"}


@router.patch("/{agreement_id}/subcontractor-response", dependencies=[Depends(require_role(RoleEnum.admin))])
async def record_response(
    agreement_id: uuid.UUID,
    payload: SubcontractorResponsePayload,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    res = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    agreement = res.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")

    try:
        await record_subcontractor_response(db, agreement, payload.response_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "status": "success",
        "agreement_status": agreement.current_status.value,
        "is_executed": agreement.is_executed,
    }


@router.post("/{agreement_id}/resolution-sheet", dependencies=[Depends(require_role(RoleEnum.admin))])
async def create_resolution(
    agreement_id: uuid.UUID,
    payload: ResolutionSheetCreatePayload,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(RoleEnum.admin)),
) -> dict:
    res = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    agreement = res.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")

    rows = await create_resolution_sheet(
        db,
        agreement,
        current_user,
        [item.model_dump() for item in payload.items],
    )
    return {
        "status": "success",
        "items": [
            {
                "id": str(row.id),
                "subcontractor_comment": row.subcontractor_comment,
                "clause_reference": row.clause_reference,
                "ai_suggested_response": row.ai_suggested_response,
            }
            for row in rows
        ],
    }
