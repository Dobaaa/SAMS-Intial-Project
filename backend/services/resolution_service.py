from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.agreement import Agreement, AgreementStatusEnum
from models.resolution import CommentsResolutionSheet
from models.user import RoleEnum, User
from models.workflow import WorkflowStep, WorkflowStepStatusEnum
from services.ai_service import suggest_responses


async def record_subcontractor_response(
    db: AsyncSession,
    agreement: Agreement,
    response_type: str,
) -> None:
    if response_type == "signed":
        agreement.execution_date = date.today()
        agreement.is_executed = True
        agreement.current_status = AgreementStatusEnum.completed
        agreement.status_updated_on = datetime.now(UTC)
    elif response_type == "comments":
        agreement.current_status = AgreementStatusEnum.under_bgcc_revision
        agreement.status_updated_on = datetime.now(UTC)
    else:
        raise ValueError("response_type must be 'signed' or 'comments'")
    await db.commit()


async def create_resolution_sheet(
    db: AsyncSession,
    agreement: Agreement,
    actor: User,
    items: list[dict[str, str | None]],
) -> list[CommentsResolutionSheet]:
    created: list[CommentsResolutionSheet] = []
    for item in items:
        row = CommentsResolutionSheet(
            agreement_id=agreement.id,
            subcontractor_comment=(item.get("subcontractor_comment") or "").strip(),
            clause_reference=item.get("clause_reference"),
            last_edited_by=actor.id,
            is_resolved=False,
        )
        db.add(row)
        created.append(row)
    await db.commit()
    for row in created:
        await db.refresh(row)

    # Prefill AI suggestions (Task 10 function 4).
    try:
        ai_result = await suggest_responses(db, str(agreement.id))
        mapped = {
            str(item.get("comment_id")): item.get("suggested_response", "")
            for item in (ai_result.data or [])
            if isinstance(item, dict)
        }
        for row in created:
            if str(row.id) in mapped:
                row.ai_suggested_response = str(mapped[str(row.id)])
        await db.commit()
    except Exception:
        # Keep sheet creation resilient even if AI call fails.
        await db.rollback()
        for row in created:
            db.add(row)
        await db.commit()

    return created


async def get_resolution_rows(db: AsyncSession, agreement_id: uuid.UUID) -> list[CommentsResolutionSheet]:
    result = await db.execute(
        select(CommentsResolutionSheet)
        .where(CommentsResolutionSheet.agreement_id == agreement_id)
        .order_by(CommentsResolutionSheet.created_at.asc())
    )
    return result.scalars().all()


async def update_resolution_item(
    db: AsyncSession,
    row: CommentsResolutionSheet,
    actor: User,
    payload: dict,
) -> CommentsResolutionSheet:
    for key in ("ai_suggested_response", "pd_response", "om_response", "final_response", "is_resolved"):
        if key in payload:
            setattr(row, key, payload[key])
    row.last_edited_by = actor.id
    row.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return row


async def submit_resolution_for_approval(db: AsyncSession, agreement: Agreement) -> None:
    # Remove stale returned/pending resolution steps if any, keep history otherwise.
    existing = await db.execute(
        select(WorkflowStep).where(
            and_(
                WorkflowStep.agreement_id == agreement.id,
                WorkflowStep.step_name.in_(["Resolution - Operation Manager", "Resolution - General Manager"]),
            )
        )
    )
    if existing.scalars().first():
        return

    for step_name, order, role in [
        ("Resolution - Operation Manager", 1, RoleEnum.operation_manager),
        ("Resolution - General Manager", 2, RoleEnum.gm),
    ]:
        db.add(
            WorkflowStep(
                agreement_id=agreement.id,
                step_name=step_name,
                step_order=order,
                role_required=role,
                status=WorkflowStepStatusEnum.pending,
            )
        )

    agreement.current_status = AgreementStatusEnum.under_bgcc_revision
    agreement.status_updated_on = datetime.now(UTC)
    await db.commit()
