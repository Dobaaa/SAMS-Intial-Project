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
from services.pdf_service import generate_agreement_pdf

router = APIRouter(tags=["pdf"])


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
