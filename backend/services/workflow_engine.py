from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.agreement import Agreement, AgreementStatusEnum
from models.user import RoleEnum, User
from models.workflow import WorkflowComment, WorkflowStep, WorkflowStepStatusEnum
from services.email_service import send_email


def _step_to_dict(step: WorkflowStep) -> dict:
    return {
        "id": str(step.id),
        "agreement_id": str(step.agreement_id),
        "step_name": step.step_name,
        "step_order": step.step_order,
        "role_required": step.role_required.value,
        "status": step.status.value,
        "assigned_user_id": str(step.assigned_user_id) if step.assigned_user_id else None,
        "acted_by": str(step.acted_by) if step.acted_by else None,
        "acted_at": step.acted_at.isoformat() if step.acted_at else None,
    }


async def get_pending_for_role(db: AsyncSession, role: RoleEnum) -> list[dict]:
    result = await db.execute(
        select(WorkflowStep)
        .where(
            and_(
                WorkflowStep.role_required == role,
                WorkflowStep.status == WorkflowStepStatusEnum.pending,
            )
        )
        .options(selectinload(WorkflowStep.agreement))
        .order_by(WorkflowStep.created_at.asc())
    )
    steps = result.scalars().all()

    pending_items: list[dict] = []
    for step in steps:
        if step.step_order > 1:
            prev_res = await db.execute(
                select(WorkflowStep).where(
                    and_(
                        WorkflowStep.agreement_id == step.agreement_id,
                        WorkflowStep.step_order == step.step_order - 1,
                    )
                )
            )
            prev_step = prev_res.scalar_one_or_none()
            if prev_step and prev_step.status != WorkflowStepStatusEnum.approved:
                continue

        pending_items.append(
            {
                "step": _step_to_dict(step),
                "agreement": {
                    "id": str(step.agreement.id),
                    "reference_number": step.agreement.reference_number,
                    "current_status": step.agreement.current_status.value,
                },
            }
        )
    return pending_items


async def approve_step(db: AsyncSession, step: WorkflowStep, actor: User) -> None:
    step.status = WorkflowStepStatusEnum.approved
    step.acted_by = actor.id
    step.acted_at = datetime.now(UTC)

    agreement = await db.get(Agreement, step.agreement_id)

    # Notify next role when a step is approved.
    if step.step_order < 4:
        next_res = await db.execute(
            select(WorkflowStep).where(
                and_(
                    WorkflowStep.agreement_id == step.agreement_id,
                    WorkflowStep.step_order == step.step_order + 1,
                )
            )
        )
        next_step = next_res.scalar_one_or_none()
        if next_step:
            recipients_res = await db.execute(
                select(User).where(User.role == next_step.role_required, User.is_active.is_(True))
            )
            recipients = recipients_res.scalars().all()
            for recipient in recipients:
                await send_email(
                    to_email=recipient.email,
                    subject=f"SAMS Review Required - {agreement.reference_number if agreement else step.agreement_id}",
                    body=(
                        f"Agreement: {agreement.reference_number if agreement else step.agreement_id}\n"
                        f"Current step: {next_step.step_name}\n"
                        f"Please review and take action."
                    ),
                )

    if step.step_order == 4:
        if agreement:
            agreement.gm_approval_date = date.today()
            agreement.current_status = AgreementStatusEnum.under_internal_review
            agreement.status_updated_on = datetime.now(UTC)
            admin_result = await db.execute(select(User).where(User.role == RoleEnum.admin, User.is_active.is_(True)))
            for admin in admin_result.scalars().all():
                await send_email(
                    to_email=admin.email,
                    subject=f"SAMS Final Internal Approval - {agreement.reference_number}",
                    body=(
                        f"Agreement {agreement.reference_number} has completed internal approvals.\n"
                        "You can proceed with PDF generation and subcontractor forwarding."
                    ),
                )

    await db.commit()


async def return_step(
    db: AsyncSession,
    step: WorkflowStep,
    actor: User,
    comment_text: str,
    clause_reference: str | None = None,
) -> WorkflowComment:
    if not comment_text.strip():
        raise ValueError("comment_text cannot be empty")

    step.status = WorkflowStepStatusEnum.returned
    step.acted_by = actor.id
    step.acted_at = datetime.now(UTC)

    comment = WorkflowComment(
        workflow_step_id=step.id,
        agreement_id=step.agreement_id,
        original_author_id=actor.id,
        last_edited_by_id=actor.id,
        comment_text=comment_text.strip(),
        clause_reference=clause_reference,
    )
    db.add(comment)
    await db.flush()

    agreement = await db.get(Agreement, step.agreement_id)
    if agreement:
        agreement.current_status = AgreementStatusEnum.under_drafting
        agreement.status_updated_on = datetime.now(UTC)

    admin_result = await db.execute(select(User).where(User.role == RoleEnum.admin, User.is_active.is_(True)))
    admin_users = admin_result.scalars().all()
    for admin in admin_users:
        await send_email(
            to_email=admin.email,
            subject=f"SAMS Return Notice - {agreement.reference_number if agreement else step.agreement_id}",
            body=(
                f"Agreement returned by: {actor.name}\n"
                f"Step: {step.step_name}\n"
                f"Comment: {comment.comment_text}\n"
                f"Clause Reference: {clause_reference or 'N/A'}"
            ),
        )

    await db.commit()
    await db.refresh(comment)
    return comment


async def resubmit_agreement(db: AsyncSession, agreement: Agreement) -> None:
    res = await db.execute(
        select(WorkflowStep)
        .where(
            and_(
                WorkflowStep.agreement_id == agreement.id,
                WorkflowStep.status == WorkflowStepStatusEnum.returned,
            )
        )
        .order_by(WorkflowStep.step_order.asc())
    )
    step = res.scalars().first()
    if not step:
        return
    step.status = WorkflowStepStatusEnum.pending
    step.acted_by = None
    step.acted_at = None
    agreement.current_status = AgreementStatusEnum.under_internal_review
    agreement.status_updated_on = datetime.now(UTC)
    await db.commit()


async def get_workflow_agreement_summary(db: AsyncSession, agreement_id: str) -> dict | None:
    agreement_result = await db.execute(
        select(Agreement).where(Agreement.id == agreement_id).options(selectinload(Agreement.workflow_steps))
    )
    agreement = agreement_result.scalar_one_or_none()
    if not agreement:
        return None

    comments_result = await db.execute(
        select(WorkflowComment)
        .where(WorkflowComment.agreement_id == agreement.id)
        .order_by(WorkflowComment.created_at.asc())
    )
    comments = comments_result.scalars().all()

    return {
        "agreement": {
            "id": str(agreement.id),
            "reference_number": agreement.reference_number,
            "current_status": agreement.current_status.value,
            "gm_approval_date": agreement.gm_approval_date.isoformat() if agreement.gm_approval_date else None,
        },
        "steps": [_step_to_dict(s) for s in sorted(agreement.workflow_steps, key=lambda x: x.step_order)],
        "comments": [
            {
                "id": str(c.id),
                "workflow_step_id": str(c.workflow_step_id),
                "comment_text": c.comment_text,
                "clause_reference": c.clause_reference,
                "status": c.status.value,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in comments
        ],
    }
