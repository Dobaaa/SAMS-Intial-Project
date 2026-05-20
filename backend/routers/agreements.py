import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from middleware.rbac import get_current_user, require_role
from models.agreement import Agreement, AgreementFieldValue, AgreementStatusEnum, AppendixConfig, Project, Subcontractor
from models.master import MasterField
from models.user import RoleEnum, User
import logging

from services.agreement_service import create_draft_agreement, submit_for_review, update_agreement_fields
from services.pdf_service import generate_agreement_pdf
from services.resolution_service import create_resolution_sheet, record_subcontractor_response
from services.workflow_engine import all_main_steps_approved, resubmit_agreement

log = logging.getLogger(__name__)

router = APIRouter(prefix="/agreements", tags=["agreements"])
subcontractors_router = APIRouter(prefix="/subcontractors", tags=["subcontractors"])
projects_router = APIRouter(prefix="/projects", tags=["projects"])


@projects_router.get("/")
async def list_projects(
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> list[dict]:
    """Return saved projects (incl. BGCC predefined ones) so the wizard can
    offer a dropdown that autofills name / site no / location / employer /
    engineer / reference. Ordered by name for predictable picker UX."""
    from models.agreement import Project

    res = await db.execute(select(Project).order_by(Project.project_name.asc()))
    return [
        {
            "id": str(p.id),
            "project_name": p.project_name,
            "project_code": p.project_code,
            "project_location": p.project_location or "",
            "employer_name": p.employer_name or "",
            "engineer_name": p.engineer_name or "",
            "reference": p.reference or "",
        }
        for p in res.scalars().all()
    ]


@subcontractors_router.get("/")
async def list_subcontractors(
    search: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> list[dict]:
    """Return previously-saved subcontractors so the wizard can offer auto-fill.

    Optional ``search`` does a case-insensitive substring match on
    company_name. Results are capped at ``limit`` (max 200) and ordered by
    company_name for predictable picker UX.
    """
    if limit > 200:
        limit = 200
    stmt = select(Subcontractor)
    if search:
        stmt = stmt.where(Subcontractor.company_name.ilike(f"%{search.strip()}%"))
    stmt = stmt.order_by(Subcontractor.company_name.asc()).limit(limit)
    res = await db.execute(stmt)
    rows = res.scalars().all()
    return [
        {
            "id": str(row.id),
            "company_name": row.company_name,
            "po_box": row.po_box or "",
            "trade_licence_no": row.trade_licence_no or "",
            "contact_person": row.contact_person or "",
            "email": row.email or "",
            "phone": row.phone or "",
            "address": row.address or "",
        }
        for row in rows
    ]


class ProjectPayload(BaseModel):
    project_name: str
    project_code: str
    project_location: str | None = None
    employer_name: str | None = None
    engineer_name: str | None = None
    reference: str | None = None


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
    # Optional: per-field-id flag. True locks the value as a manual override
    # (cascade skips it). False / omitted preserves the existing flag — pass
    # False to a previously-locked field to reset it back to auto.
    overrides: dict[str, bool] | None = None


class SubcontractorResponsePayload(BaseModel):
    response_type: str
    signed_scan_path: str | None = None
    comments_count: int | None = None


class ResolutionItemCreate(BaseModel):
    subcontractor_comment: str
    clause_reference: str | None = None
    original_clause_text: str | None = None


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
    except IntegrityError as exc:
        await db.rollback()
        msg = str(exc.orig) if exc.orig else str(exc)
        if "agreements_reference_number_key" in msg:
            detail = (
                f"Reference number '{payload.reference_number}' already exists. "
                "Leave the reference field blank to auto-generate a unique number."
            )
        elif "projects_project_code_key" in msg:
            detail = f"Project code '{payload.project.project_code}' already exists with different details."
        else:
            detail = "Could not create agreement: a unique field already has that value."
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc

    return {
        "id": str(agreement.id),
        "reference_number": agreement.reference_number,
        "status": agreement.current_status.value,
    }


class UpdatePartiesPayload(BaseModel):
    project: ProjectPayload
    subcontractor: SubcontractorPayload


@router.patch("/{agreement_id}/parties", dependencies=[Depends(require_role(RoleEnum.admin))])
async def update_parties(
    agreement_id: uuid.UUID,
    payload: UpdatePartiesPayload,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Update the Project + Subcontractor rows linked to an existing draft.

    Used by the wizard's edit mode (Step 1) so admin can amend project and
    subcontractor details without creating a new agreement. project_code is
    the unique key — if changed, we look up an existing Project with that
    code and re-link, otherwise update the current row's code in place.
    """
    res = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    agreement = res.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")
    if agreement.is_executed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agreement is locked after execution")

    project_data = payload.project.model_dump()
    subcontractor_data = payload.subcontractor.model_dump()

    project = await db.get(Project, agreement.project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked project missing")

    new_code = project_data["project_code"]
    if new_code != project.project_code:
        existing = (
            await db.execute(
                select(Project).where(Project.project_code == new_code, Project.id != project.id)
            )
        ).scalar_one_or_none()
        if existing is not None:
            agreement.project_id = existing.id
            project = existing
        else:
            project.project_code = new_code

    project.project_name = project_data["project_name"]
    project.project_location = project_data["project_location"]
    project.employer_name = project_data["employer_name"]
    project.engineer_name = project_data["engineer_name"]

    subcontractor = await db.get(Subcontractor, agreement.subcontractor_id)
    if not subcontractor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked subcontractor missing")
    for key, value in subcontractor_data.items():
        setattr(subcontractor, key, value)

    agreement.updated_at = datetime.now(UTC)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        msg = str(exc.orig) if exc.orig else str(exc)
        if "projects_project_code_key" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project code '{new_code}' already exists.",
            ) from exc
        raise

    return {"status": "success"}


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
    await update_agreement_fields(
        db, agreement, current_user, payload.values, overrides=payload.overrides
    )

    # Return the full {field_id: entered_value} map so the wizard can pick up
    # backend-cascaded values (e.g. F08 -> C03 -> A09) without a follow-up GET.
    rows = await db.execute(
        select(AgreementFieldValue).where(AgreementFieldValue.agreement_id == agreement_id)
    )
    values = {r.field_id: (r.entered_value or "") for r in rows.scalars().all()}
    return {"status": "success", "values": values}


@router.get("/{agreement_id}/fields", dependencies=[Depends(require_role(RoleEnum.admin))])
async def get_fields(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    res = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")
    rows = await db.execute(
        select(AgreementFieldValue).where(AgreementFieldValue.agreement_id == agreement_id)
    )
    values = {r.field_id: (r.entered_value or "") for r in rows.scalars().all()}
    return {"values": values}


@router.get("/{agreement_id}")
async def get_agreement(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> dict:
    """One-call hydrate for the wizard's edit-existing-draft flow.

    Returns project + subcontractor payloads in the same shape Step 1 sends,
    plus the full {field_id: entered_value} map and the agreement metadata.
    """
    from sqlalchemy.orm import selectinload

    res = await db.execute(
        select(Agreement)
        .where(Agreement.id == agreement_id)
        .options(selectinload(Agreement.project), selectinload(Agreement.subcontractor))
    )
    agreement = res.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")

    rows = await db.execute(
        select(AgreementFieldValue).where(AgreementFieldValue.agreement_id == agreement_id)
    )
    values = {r.field_id: (r.entered_value or "") for r in rows.scalars().all()}

    return {
        "id": str(agreement.id),
        "reference_number": agreement.reference_number,
        "current_status": agreement.current_status.value,
        "is_executed": agreement.is_executed,
        "project": {
            "project_name": agreement.project.project_name,
            "project_code": agreement.project.project_code,
            "project_location": agreement.project.project_location or "",
            "employer_name": agreement.project.employer_name or "",
            "engineer_name": agreement.project.engineer_name or "",
        },
        "subcontractor": {
            "company_name": agreement.subcontractor.company_name,
            "po_box": agreement.subcontractor.po_box or "",
            "trade_licence_no": agreement.subcontractor.trade_licence_no or "",
            "contact_person": agreement.subcontractor.contact_person or "",
            "email": agreement.subcontractor.email or "",
            "phone": agreement.subcontractor.phone or "",
            "address": agreement.subcontractor.address or "",
        },
        "values": values,
    }


@router.delete("/{agreement_id}", dependencies=[Depends(require_role(RoleEnum.admin))])
async def delete_agreement(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Delete an in-progress agreement.

    Restricted to drafts that have not yet moved past internal review and
    have no GM approval on file. Cascades clean up workflow_steps,
    appendix_config, agreement_field_values, and resolution items via the
    relationship cascades on Agreement.
    """
    res = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    agreement = res.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")

    if agreement.is_executed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete an executed agreement",
        )
    deletable_statuses = {
        AgreementStatusEnum.under_drafting,
        AgreementStatusEnum.under_bgcc_revision,
        AgreementStatusEnum.under_internal_review,
    }
    if agreement.current_status not in deletable_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Agreement cannot be deleted at this stage "
                f"(current: {agreement.current_status.value})."
            ),
        )
    if agreement.gm_approval_date is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete an agreement that already has GM approval recorded",
        )

    await db.delete(agreement)
    await db.commit()
    return {"status": "deleted", "id": str(agreement_id)}


@router.post("/{agreement_id}/submit", dependencies=[Depends(require_role(RoleEnum.admin))])
async def submit_agreement(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    res = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    agreement = res.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")
    await submit_for_review(db, agreement)
    # Best-effort: generate the PDF so reviewers always have a copy to read.
    # If WeasyPrint blows up we still leave the workflow in place; admin can
    # retry from the dashboard.
    try:
        await generate_agreement_pdf(db, str(agreement_id), current_user)
    except Exception:
        log.exception("Auto-PDF generation failed for agreement %s", agreement_id)
    return {"status": "submitted"}


@router.post("/{agreement_id}/resubmit", dependencies=[Depends(require_role(RoleEnum.admin))])
async def resubmit_returned_agreement(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    res = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    agreement = res.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")
    await resubmit_agreement(db, agreement)
    try:
        await generate_agreement_pdf(db, str(agreement_id), current_user)
    except Exception:
        log.exception("Auto-PDF regeneration failed for agreement %s", agreement_id)
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
                "is_manual_override": value.is_manual_override if value else False,
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
        # Flat review model: forwarding is gated on every reviewer role
        # (PD, Accounts, OM, GM) having approved.
        if not await all_main_steps_approved(db, agreement.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="All reviewer roles (PD, Accounts, OM, GM) must approve before forwarding to the subcontractor.",
            )
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
                "original_clause_text": row.original_clause_text,
                "ai_suggested_response": row.ai_suggested_response,
            }
            for row in rows
        ],
    }
