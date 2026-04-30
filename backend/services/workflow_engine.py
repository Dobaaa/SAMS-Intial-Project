from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.agreement import Agreement, AgreementStatusEnum
from models.user import RoleEnum, User
from models.workflow import CommentStatusEnum, WorkflowComment, WorkflowStep, WorkflowStepStatusEnum
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
            # Stay within the same chain (main vs resolution); both share
            # the workflow_steps table so step_order=1 alone matches two rows.
            is_resolution = _is_resolution_step(step)
            prev_res = await db.execute(
                select(WorkflowStep).where(
                    and_(
                        WorkflowStep.agreement_id == step.agreement_id,
                        WorkflowStep.step_order == step.step_order - 1,
                        (
                            WorkflowStep.step_name.in_(RESOLUTION_STEP_NAMES)
                            if is_resolution
                            else ~WorkflowStep.step_name.in_(RESOLUTION_STEP_NAMES)
                        ),
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


RESOLUTION_STEP_NAMES = {"Resolution - Operation Manager", "Resolution - General Manager"}


def _is_resolution_step(step: WorkflowStep) -> bool:
    return step.step_name in RESOLUTION_STEP_NAMES


async def _notify_admins_agreement_ready_to_forward(
    db: AsyncSession, agreement: Agreement
) -> None:
    admin_result = await db.execute(
        select(User).where(User.role == RoleEnum.admin, User.is_active.is_(True))
    )
    for admin in admin_result.scalars().all():
        await send_email(
            to_email=admin.email,
            subject=f"SAMS Ready for Subcontractor - {agreement.reference_number}",
            body=(
                f"Agreement {agreement.reference_number} has completed its internal\n"
                "review / resolution cycle. You can now generate the PDF and forward\n"
                "it to the subcontractor."
            ),
        )


async def approve_step(db: AsyncSession, step: WorkflowStep, actor: User) -> None:
    step.status = WorkflowStepStatusEnum.approved
    step.acted_by = actor.id
    step.acted_at = datetime.now(UTC)

    agreement = await db.get(Agreement, step.agreement_id)
    is_resolution = _is_resolution_step(step)
    # Main chain has 4 steps; resolution chain has 2 (OM -> GM).
    last_order = 2 if is_resolution else 4

    # Notify the next role for mid-chain approvals (both kinds).
    if step.step_order < last_order:
        next_res = await db.execute(
            select(WorkflowStep).where(
                and_(
                    WorkflowStep.agreement_id == step.agreement_id,
                    WorkflowStep.step_order == step.step_order + 1,
                    # Stay within the same chain so resolution-OM's "next"
                    # doesn't accidentally pick up a stale main-chain step.
                    (
                        WorkflowStep.step_name.in_(RESOLUTION_STEP_NAMES)
                        if is_resolution
                        else ~WorkflowStep.step_name.in_(RESOLUTION_STEP_NAMES)
                    ),
                )
            )
        )
        next_step = next_res.scalar_one_or_none()
        if next_step:
            recipients_res = await db.execute(
                select(User).where(User.role == next_step.role_required, User.is_active.is_(True))
            )
            for recipient in recipients_res.scalars().all():
                await send_email(
                    to_email=recipient.email,
                    subject=f"SAMS Review Required - {agreement.reference_number if agreement else step.agreement_id}",
                    body=(
                        f"Agreement: {agreement.reference_number if agreement else step.agreement_id}\n"
                        f"Current step: {next_step.step_name}\n"
                        "Please review and take action."
                    ),
                )

    # Terminal approvals.
    if agreement and step.step_order == last_order:
        if is_resolution:
            # Resolution cycle complete -- Admin can now send the revised
            # agreement to the subcontractor. Status stays under_bgcc_revision
            # until Admin triggers POST /api/agreements/{id}/send-to-subcontractor.
            pass
        else:
            # Main chain GM approval.
            agreement.gm_approval_date = date.today()
            agreement.current_status = AgreementStatusEnum.under_internal_review
        agreement.status_updated_on = datetime.now(UTC)
        await _notify_admins_agreement_ready_to_forward(db, agreement)

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
        # Per spec: returns flip the agreement to under_bgcc_revision so
        # admin sees a distinct state from a brand-new under_drafting and
        # the dashboard surfaces "Resubmit for Review" + the returned-
        # comments badge. Resubmit restarts the whole chain from step 1
        # (PD), so any prior approvals on this agreement are wiped.
        agreement.current_status = AgreementStatusEnum.under_bgcc_revision
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
    # Spec: resubmit restarts the WHOLE chain from step 1 (PD for the main
    # chain, Resolution-OM for the resolution chain) rather than just
    # reactivating the returned step. Scope to the chain of the returned
    # step so a main-chain return doesn't wipe resolution progress and
    # vice versa.
    returned_res = await db.execute(
        select(WorkflowStep)
        .where(
            and_(
                WorkflowStep.agreement_id == agreement.id,
                WorkflowStep.status == WorkflowStepStatusEnum.returned,
            )
        )
        .order_by(WorkflowStep.step_order.asc())
    )
    returned_step = returned_res.scalars().first()
    if not returned_step:
        return

    in_resolution = _is_resolution_step(returned_step)
    chain_filter = (
        WorkflowStep.step_name.in_(RESOLUTION_STEP_NAMES)
        if in_resolution
        else ~WorkflowStep.step_name.in_(RESOLUTION_STEP_NAMES)
    )
    chain_res = await db.execute(
        select(WorkflowStep).where(
            and_(WorkflowStep.agreement_id == agreement.id, chain_filter)
        )
    )
    for s in chain_res.scalars().all():
        s.status = WorkflowStepStatusEnum.pending
        s.acted_by = None
        s.acted_at = None

    agreement.current_status = AgreementStatusEnum.under_internal_review
    agreement.status_updated_on = datetime.now(UTC)

    # Resubmit implies admin has addressed the returned comments. Mark every
    # open WorkflowComment on this agreement as resolved so the dashboard
    # badge clears and the next reviewer sees them as historically addressed.
    open_comments = await db.execute(
        select(WorkflowComment).where(
            WorkflowComment.agreement_id == agreement.id,
            WorkflowComment.status != CommentStatusEnum.resolved,
        )
    )
    for c in open_comments.scalars().all():
        c.status = CommentStatusEnum.resolved

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
