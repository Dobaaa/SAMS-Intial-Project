import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from middleware.rbac import get_current_user, require_role
from models.agreement import Agreement, AgreementFieldValue, AgreementStatusEnum, AppendixConfig
from models.master import MasterField
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


class AppendixRowUpdate(BaseModel):
    show_in_appendix: bool | None = None
    admin_extra_note: str | None = None
    sort_order: int | None = None


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


@router.get("/{agreement_id}/appendix")
async def get_appendix(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> list[dict]:
    """Return the appendix rows for an agreement.

    Joins `appendix_config` with `master_fields` (for the row label + clause
    ref + auto-source metadata) and `agreement_field_values` (for the
    current value). Sorted by the admin-set sort_order.
    """
    # Agreement must exist to scope the query.
    agreement_res = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    if not agreement_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")

    config_res = await db.execute(
        select(AppendixConfig)
        .where(AppendixConfig.agreement_id == agreement_id)
        .order_by(AppendixConfig.sort_order.asc())
    )
    configs = config_res.scalars().all()

    master_res = await db.execute(select(MasterField))
    master_map = {mf.field_id: mf for mf in master_res.scalars().all()}

    value_res = await db.execute(
        select(AgreementFieldValue).where(AgreementFieldValue.agreement_id == agreement_id)
    )
    value_map = {v.field_id: v for v in value_res.scalars().all()}

    rows: list[dict] = []
    for cfg in configs:
        mf = master_map.get(cfg.field_id)
        if not mf:
            continue
        value = value_map.get(cfg.field_id)
        rows.append(
            {
                "field_id": cfg.field_id,
                "row_label": mf.appendix_row_label or mf.field_label,
                "clause_ref": mf.appendix_clause_ref or mf.clause_number,
                "current_value": value.entered_value if value else None,
                "is_modified_from_default": value.is_modified_from_default if value else False,
                "auto_source_field_id": mf.auto_source_field_id,
                "show_in_appendix": cfg.show_in_appendix,
                "admin_extra_note": cfg.admin_extra_note,
                "sort_order": cfg.sort_order,
            }
        )
    return rows


@router.put(
    "/{agreement_id}/appendix/{field_id}",
    dependencies=[Depends(require_role(RoleEnum.admin))],
)
async def update_appendix_row(
    agreement_id: uuid.UUID,
    field_id: str,
    payload: AppendixRowUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(RoleEnum.admin)),
) -> dict:
    res = await db.execute(
        select(AppendixConfig).where(
            AppendixConfig.agreement_id == agreement_id,
            AppendixConfig.field_id == field_id,
        )
    )
    row = res.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appendix row not found")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return {"status": "noop"}
    for key, value in changes.items():
        setattr(row, key, value)
    row.last_modified_by = current_user.id
    row.last_modified_at = datetime.now(UTC)
    await db.commit()
    return {"status": "success"}


@router.post("/{agreement_id}/send-to-subcontractor", dependencies=[Depends(require_role(RoleEnum.admin))])
async def send_to_subcontractor(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Transition the agreement to the appropriate subcontractor-facing status.

    Called by Admin after:
      - The main approval chain has completed (GM approved) -- moves to
        draft_forwarded_to_subcontractor for the first time.
      - The resolution chain has completed (OM + GM approved revisions) --
        moves to under_subcontractor_signature for signature.
    """
    res = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    agreement = res.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")

    if agreement.current_status == AgreementStatusEnum.under_internal_review:
        agreement.current_status = AgreementStatusEnum.draft_forwarded_to_subcontractor
    elif agreement.current_status == AgreementStatusEnum.under_bgcc_revision:
        agreement.current_status = AgreementStatusEnum.under_subcontractor_signature
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Agreement is not in a status that can be forwarded to the subcontractor "
                f"(current: {agreement.current_status.value})."
            ),
        )

    agreement.status_updated_on = datetime.now(UTC)
    await db.commit()
    return {
        "status": "success",
        "agreement_status": agreement.current_status.value,
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
