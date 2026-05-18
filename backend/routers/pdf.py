import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from middleware.rbac import get_current_user, require_role
from models.ai_review import DeviationReport, PDFOutput
from models.user import RoleEnum, User
from services.deviation_service import generate_deviation_report
from services.docx_pdf_service import MASTER_DOCX, render_agreement_docx_to_pdf
from services.pdf_service import generate_agreement_pdf

router = APIRouter(tags=["pdf"])

# In-memory cache for the "blank master" PDF. Keyed by the master docx
# mtime so a redeploy that re-tokenizes the master invalidates it.
_BLANK_MASTER_CACHE: dict[float, bytes] = {}


@router.post("/pdf/{agreement_id}/generate", dependencies=[Depends(require_role(RoleEnum.admin))])
async def generate_pdf(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        output = await generate_agreement_pdf(db, str(agreement_id), current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "status": "success",
        "pdf_output_id": str(output.id),
        "file_path": output.file_path,
    }


@router.get("/pdf/master/preview")
async def preview_master_pdf(
    _: User = Depends(get_current_user),
) -> Response:
    """Return the blank-template PDF — the master docx rendered with all
    {{FIELD_ID}} tokens substituted with empty strings.

    This is the "Original / Base Version – 42 Pages" referenced in
    Rev 01 item 17-extension's side-by-side comparison: identical for every
    agreement, no admin-specific values filled in. The Compare view embeds
    it on the left, with the agreement's actual PDF on the right.

    Cached in-memory keyed by the master docx mtime — a new tokenized
    master automatically invalidates the cache without a restart.

    Declared BEFORE the /pdf/{agreement_id}/preview route so FastAPI
    matches the literal "master" path here rather than trying to parse
    it as a UUID and erroring with 422.
    """
    if not MASTER_DOCX.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Master docx is missing",
        )
    mtime = MASTER_DOCX.stat().st_mtime
    cached = _BLANK_MASTER_CACHE.get(mtime)
    if cached is None:
        with tempfile.TemporaryDirectory(prefix="sams_master_") as tmp:
            cached = render_agreement_docx_to_pdf({}, tmp)
        _BLANK_MASTER_CACHE.clear()  # drop older entries on regeneration
        _BLANK_MASTER_CACHE[mtime] = cached
    return Response(
        content=cached,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="sca_master.pdf"'},
    )


@router.get("/pdf/{agreement_id}/preview/with_changes")
async def preview_pdf_with_changes(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> Response:
    """Render the agreement with pending clause revisions surfaced as
    Word track-changes (<w:del> + <w:ins>) inside the PDF.

    Phase 4 v2.2 — powers the Compare view's "Show pending changes"
    toggle. Live render, no caching: the output depends on every pending
    revision's current modified_text. ~3s per request.
    """
    from models.agreement import Agreement, AgreementClauseRevision, ClauseRevisionStatus
    from services.docx_pdf_service import render_agreement_docx_to_pdf
    from services.pdf_service import _collect_field_values, _load_agreement_bundle

    agreement = await _load_agreement_bundle(db, str(agreement_id))
    if agreement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")

    value_map = _collect_field_values(agreement.field_values)
    if agreement.reference_number:
        value_map["REFERENCE"] = agreement.reference_number
    from services.pdf_service import _inject_percentage_amounts
    _inject_percentage_amounts(value_map)

    rev_res = await db.execute(
        select(AgreementClauseRevision).where(
            AgreementClauseRevision.agreement_id == agreement_id,
        )
    )
    revisions = rev_res.scalars().all()
    accepted = [
        (r.clause_hash, r.modified_text)
        for r in revisions
        if r.status == ClauseRevisionStatus.accepted.value
    ]
    pending = [
        (r.clause_hash, r.original_text, r.modified_text)
        for r in revisions
        if r.status == ClauseRevisionStatus.pending.value
    ]

    with tempfile.TemporaryDirectory(prefix=f"sams_changes_{agreement_id}_") as tmp:
        pdf_bytes = render_agreement_docx_to_pdf(
            value_map,
            tmp,
            accepted_revisions=accepted,
            pending_revisions=pending,
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="sca_{agreement.reference_number}_with_changes.pdf"'
        },
    )


@router.get("/pdf/{agreement_id}/preview")
async def preview_pdf(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> Response:
    result = await db.execute(
        select(PDFOutput)
        .where(PDFOutput.agreement_id == agreement_id)
        .order_by(desc(PDFOutput.generated_at))
        .limit(1)
    )
    output = result.scalar_one_or_none()
    if not output:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No generated PDF found")

    path = Path(output.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated PDF file is missing")

    return Response(
        content=path.read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )


@router.get("/agreements/{agreement_id}/deviation-report")
async def get_deviation_report(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    existing_result = await db.execute(
        select(DeviationReport)
        .where(DeviationReport.agreement_id == agreement_id)
        .order_by(desc(DeviationReport.generated_at))
        .limit(1)
    )
    report = existing_result.scalar_one_or_none()
    if not report:
        report = await generate_deviation_report(db, str(agreement_id), current_user, force_regenerate=False)

    path = Path(report.pdf_path or "")
    if not path.exists():
        report = await generate_deviation_report(db, str(agreement_id), current_user, force_regenerate=True)
        path = Path(report.pdf_path or "")
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deviation report file is missing")

    return Response(
        content=path.read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )


@router.post(
    "/agreements/{agreement_id}/deviation-report/regenerate",
    dependencies=[Depends(require_role(RoleEnum.admin))],
)
async def regenerate_deviation_report(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    report = await generate_deviation_report(db, str(agreement_id), current_user, force_regenerate=True)
    return {
        "status": "success",
        "deviation_report_id": str(report.id),
        "pdf_path": report.pdf_path,
    }
