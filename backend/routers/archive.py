import io
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from openpyxl import Workbook
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db_session
from middleware.rbac import get_current_user
from models.agreement import Agreement, AgreementFieldValue, AgreementStatusEnum, Project, Subcontractor
from models.ai_review import PDFOutput, PDFTypeEnum
from models.user import User

router = APIRouter(prefix="/archive", tags=["archive"])


STATUS_LABELS = {
    "under_drafting": "Under Drafting",
    "under_internal_review": "Under Internal Review",
    "draft_forwarded_to_subcontractor": "Draft Forwarded to Subcontractor",
    "under_subcontractor_review": "Under Subcontractor Review",
    "under_subcontractor_signature": "Under Subcontractor Signature",
    "under_bgcc_revision": "Under BGCC Revision",
    "under_gm_signature": "Under GM Signature",
    "completed": "Completed",
}


def _agreement_row(agreement: Agreement) -> dict:
    c01 = next((f for f in (agreement.field_values or []) if f.field_id == "C01"), None)
    return {
        "id": str(agreement.id),
        "reference_number": agreement.reference_number,
        "subcontractor_name": agreement.subcontractor.company_name if agreement.subcontractor else None,
        "project_name": agreement.project.project_name if agreement.project else None,
        "project_code": agreement.project.project_code if agreement.project else None,
        "scope_of_works": (c01.entered_value or "").strip() if c01 else "",
        "current_status": agreement.current_status.value,
        "status_label": STATUS_LABELS.get(agreement.current_status.value, agreement.current_status.value),
        "status_updated_on": agreement.status_updated_on.isoformat() if agreement.status_updated_on else None,
        "gm_approval_date": agreement.gm_approval_date.isoformat() if agreement.gm_approval_date else None,
        "execution_date": agreement.execution_date.isoformat() if agreement.execution_date else None,
        "is_executed": agreement.is_executed,
        "created_at": agreement.created_at.isoformat() if agreement.created_at else None,
    }


def _apply_archive_filters(query, status_filter, date_from, date_to, reference_number):  # type: ignore[no-untyped-def]
    if status_filter:
        query = query.where(Agreement.current_status == AgreementStatusEnum(status_filter))
    if date_from:
        query = query.where(Agreement.created_at >= date_from)
    if date_to:
        query = query.where(Agreement.created_at <= date_to)
    if reference_number:
        query = query.where(Agreement.reference_number.ilike(f"%{reference_number}%"))
    return query


@router.get("/projects/{project_id}")
async def archive_by_project(
    project_id: uuid.UUID,
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = None,
    date_to: date | None = None,
    reference_number: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> list[dict]:
    if status_filter:
        try:
            AgreementStatusEnum(status_filter)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status filter") from exc
    query = (
        select(Agreement)
        .where(Agreement.project_id == project_id)
        .options(
            selectinload(Agreement.project),
            selectinload(Agreement.subcontractor),
            selectinload(Agreement.field_values),
        )
        .order_by(desc(Agreement.created_at))
    )
    query = _apply_archive_filters(query, status_filter, date_from, date_to, reference_number)
    result = await db.execute(query)
    return [_agreement_row(item) for item in result.scalars().all()]


@router.get("/subcontractors/{subcontractor_id}")
async def archive_by_subcontractor(
    subcontractor_id: uuid.UUID,
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = None,
    date_to: date | None = None,
    reference_number: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> list[dict]:
    if status_filter:
        try:
            AgreementStatusEnum(status_filter)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status filter") from exc
    query = (
        select(Agreement)
        .where(Agreement.subcontractor_id == subcontractor_id)
        .options(
            selectinload(Agreement.project),
            selectinload(Agreement.subcontractor),
            selectinload(Agreement.field_values),
        )
        .order_by(desc(Agreement.created_at))
    )
    query = _apply_archive_filters(query, status_filter, date_from, date_to, reference_number)
    result = await db.execute(query)
    return [_agreement_row(item) for item in result.scalars().all()]


@router.get("/agreements")
async def list_all_archive_agreements(
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = None,
    date_to: date | None = None,
    reference_number: str | None = None,
    project_code: str | None = None,
    project_name: str | None = None,
    subcontractor_name: str | None = None,
    scope_of_works: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> list[dict]:
    """Req 8: flat listing of every agreement, no project/subcontractor id
    required — unlike /projects/{id} and /subcontractors/{id} above, which
    can't list everything. Filters cover req 10's full field list (Project
    Code / Agreement Ref / Project Name / Scope of Works / Subcontractor
    Name / Status); bucketing (req 9) is computed client-side from this
    flat response.
    """
    if status_filter:
        try:
            AgreementStatusEnum(status_filter)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status filter") from exc

    query = (
        select(Agreement)
        .join(Agreement.project)
        .join(Agreement.subcontractor)
        .options(
            selectinload(Agreement.project),
            selectinload(Agreement.subcontractor),
            selectinload(Agreement.field_values),
        )
        .order_by(desc(Agreement.created_at))
    )
    query = _apply_archive_filters(query, status_filter, date_from, date_to, reference_number)
    if project_code:
        query = query.where(Project.project_code.ilike(f"%{project_code}%"))
    if project_name:
        query = query.where(Project.project_name.ilike(f"%{project_name}%"))
    if subcontractor_name:
        query = query.where(Subcontractor.company_name.ilike(f"%{subcontractor_name}%"))
    if scope_of_works:
        query = query.join(
            AgreementFieldValue,
            and_(
                AgreementFieldValue.agreement_id == Agreement.id,
                AgreementFieldValue.field_id == "C01",
            ),
        ).where(AgreementFieldValue.entered_value.ilike(f"%{scope_of_works}%"))

    result = await db.execute(query)
    return [_agreement_row(item) for item in result.scalars().all()]


@router.get("/agreements/{agreement_id}")
async def archive_agreement_detail(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(Agreement)
        .where(Agreement.id == agreement_id)
        .options(
            selectinload(Agreement.project),
            selectinload(Agreement.subcontractor),
            selectinload(Agreement.field_values),
            selectinload(Agreement.appendix_rows),
            selectinload(Agreement.workflow_steps),
        )
    )
    agreement = result.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")
    return {
        **_agreement_row(agreement),
        "view_only": agreement.is_executed,
        "field_values": [
            {"field_id": f.field_id, "entered_value": f.entered_value, "is_modified_from_default": f.is_modified_from_default}
            for f in agreement.field_values
        ],
        "appendix_config": [
            {"field_id": a.field_id, "show_in_appendix": a.show_in_appendix, "admin_extra_note": a.admin_extra_note}
            for a in agreement.appendix_rows
        ],
        "workflow_steps": [
            {"step_name": s.step_name, "step_order": s.step_order, "status": s.status.value}
            for s in agreement.workflow_steps
        ],
    }


@router.get("/agreements/{agreement_id}/download")
async def download_executed_pdf(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> Response:
    result = await db.execute(
        select(PDFOutput)
        .where(
            and_(
                PDFOutput.agreement_id == agreement_id,
                PDFOutput.pdf_type.in_([PDFTypeEnum.executed, PDFTypeEnum.final]),
            )
        )
        .order_by(desc(PDFOutput.generated_at))
        .limit(1)
    )
    pdf_output = result.scalar_one_or_none()
    if not pdf_output:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Final executed PDF not found")
    path = Path(pdf_output.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing")
    return Response(
        content=path.read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@router.get("/export")
async def export_archive(
    project_id: uuid.UUID | None = None,
    subcontractor_id: uuid.UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = None,
    date_to: date | None = None,
    reference_number: str | None = None,
    project_code: str | None = None,
    project_name: str | None = None,
    subcontractor_name: str | None = None,
    scope_of_works: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> Response:
    """Exports the current Archive view. project_id/subcontractor_id are
    still accepted (Project View / Subcontractor View), but are now
    optional — with none of them, exports the flat/filtered listing that
    GET /archive/agreements shows."""
    if status_filter:
        try:
            AgreementStatusEnum(status_filter)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status filter") from exc

    query = (
        select(Agreement)
        .join(Agreement.project)
        .join(Agreement.subcontractor)
        .options(selectinload(Agreement.project), selectinload(Agreement.subcontractor))
    )
    if project_id:
        query = query.where(Agreement.project_id == project_id)
    if subcontractor_id:
        query = query.where(Agreement.subcontractor_id == subcontractor_id)
    if project_code:
        query = query.where(Project.project_code.ilike(f"%{project_code}%"))
    if project_name:
        query = query.where(Project.project_name.ilike(f"%{project_name}%"))
    if subcontractor_name:
        query = query.where(Subcontractor.company_name.ilike(f"%{subcontractor_name}%"))
    if scope_of_works:
        query = query.join(
            AgreementFieldValue,
            and_(
                AgreementFieldValue.agreement_id == Agreement.id,
                AgreementFieldValue.field_id == "C01",
            ),
        ).where(AgreementFieldValue.entered_value.ilike(f"%{scope_of_works}%"))
    query = _apply_archive_filters(query, status_filter, date_from, date_to, reference_number)
    query = query.order_by(desc(Agreement.created_at))
    rows = (await db.execute(query)).scalars().all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Archive"
    ws.append(["Reference No", "Project", "Subcontractor", "Status", "GM Approval Date", "Execution Date"])
    for agreement in rows:
        ws.append(
            [
                agreement.reference_number,
                agreement.project.project_name if agreement.project else "",
                agreement.subcontractor.company_name if agreement.subcontractor else "",
                STATUS_LABELS.get(agreement.current_status.value, agreement.current_status.value),
                agreement.gm_approval_date.isoformat() if agreement.gm_approval_date else "",
                agreement.execution_date.isoformat() if agreement.execution_date else "",
            ]
        )

    content = io.BytesIO()
    wb.save(content)
    content.seek(0)
    return Response(
        content=content.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="archive_export.xlsx"'},
    )
