from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.agreement import Agreement, AgreementFieldValue, AgreementStatusEnum
from models.user import RoleEnum, User
from models.workflow import CommentReaction, CommentStatusEnum, WorkflowComment, WorkflowStep, WorkflowStepStatusEnum
from services.email_service import send_email


async def _get_email_context(db: AsyncSession, agreement: Agreement) -> str:
    """Return project / subcontractor / scope lines for inclusion in email bodies."""
    from sqlalchemy.orm import selectinload as _sio

    # Load project and subcontractor if not already present on the object
    agr_res = await db.execute(
        select(Agreement)
        .where(Agreement.id == agreement.id)
        .options(_sio(Agreement.project), _sio(Agreement.subcontractor))
    )
    agr = agr_res.scalar_one_or_none() or agreement

    project_name = agr.project.project_name if agr.project else "N/A"
    subcontractor_name = agr.subcontractor.company_name if agr.subcontractor else "N/A"

    c01_res = await db.execute(
        select(AgreementFieldValue).where(
            AgreementFieldValue.agreement_id == agreement.id,
            AgreementFieldValue.field_id == "C01",
        )
    )
    c01 = c01_res.scalar_one_or_none()
    scope = (c01.entered_value or "").strip() if c01 else ""
    if len(scope) > 300:
        scope = scope[:300] + "…"
    scope = scope or "N/A"

    return (
        f"  Project:       {project_name}\n"
        f"  Subcontractor: {subcontractor_name}\n"
        f"  Scope:         {scope}"
    )


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


async def get_all_for_role(db: AsyncSession, role: RoleEnum) -> list[dict]:
    """All steps for this role (pending + approved + returned) with enriched
    agreement info (project / subcontractor names). Used by the reviewer
    sidebar and reviewer dashboard so agreements remain visible after approval.
    """
    result = await db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.role_required == role)
        .options(
            selectinload(WorkflowStep.agreement).selectinload(Agreement.project),
            selectinload(WorkflowStep.agreement).selectinload(Agreement.subcontractor),
        )
        .order_by(WorkflowStep.created_at.desc())
    )
    steps = result.scalars().all()
    return [
        {
            "step": _step_to_dict(step),
            "agreement": {
                "id": str(step.agreement.id),
                "reference_number": step.agreement.reference_number,
                "current_status": step.agreement.current_status.value,
                "project_name": step.agreement.project.project_name if step.agreement.project else None,
                "subcontractor_name": step.agreement.subcontractor.company_name if step.agreement.subcontractor else None,
            },
        }
        for step in steps
    ]


async def get_all_for_admin(db: AsyncSession) -> list[dict]:
    """Agreements visible to admin on the Workflow Review page: both
    under_internal_review (main review) and under_bgcc_revision (resolution /
    resubmit cycle). Uses the lowest-order step as the sidebar representative."""
    result = await db.execute(
        select(Agreement)
        .where(
            Agreement.current_status.in_([
                AgreementStatusEnum.under_internal_review,
                AgreementStatusEnum.under_bgcc_revision,
            ])
        )
        .options(
            selectinload(Agreement.project),
            selectinload(Agreement.subcontractor),
            selectinload(Agreement.workflow_steps),
        )
        .order_by(Agreement.status_updated_on.desc())
    )
    items = []
    for agr in result.scalars().all():
        if not agr.workflow_steps:
            continue
        rep_step = min(agr.workflow_steps, key=lambda s: s.step_order)
        items.append({
            "step": _step_to_dict(rep_step),
            "agreement": {
                "id": str(agr.id),
                "reference_number": agr.reference_number,
                "current_status": agr.current_status.value,
                "project_name": agr.project.project_name if agr.project else None,
                "subcontractor_name": agr.subcontractor.company_name if agr.subcontractor else None,
            },
        })
    return items


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
        # Both the main chain (Accounts -> PD -> OM -> GM) and the
        # resolution chain (OM -> GM) are sequential: a step only becomes
        # visible/actionable once the prior step in its own chain is
        # approved.
        if not await _previous_step_approved(db, step):
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

# Roles that get observer-only access in WorkflowReview (no approval step of their own).
OBSERVER_ROLES = {RoleEnum.admin, RoleEnum.quality_surveyor, RoleEnum.estimator, RoleEnum.project_manager}


def _is_resolution_step(step: WorkflowStep) -> bool:
    return step.step_name in RESOLUTION_STEP_NAMES


async def _previous_step_approved(db: AsyncSession, step: WorkflowStep) -> bool:
    """True if `step` is first in its chain, or the immediately-prior step
    in the same chain (main vs resolution, scoped by step_name) is approved.

    Both chains are sequential: main is Accounts(1) -> PD(2) -> OM(3) -> GM(4),
    resolution is OM(1) -> GM(2).
    """
    if step.step_order <= 1:
        return True

    chain_filter = (
        WorkflowStep.step_name.in_(RESOLUTION_STEP_NAMES)
        if _is_resolution_step(step)
        else ~WorkflowStep.step_name.in_(RESOLUTION_STEP_NAMES)
    )
    prev_res = await db.execute(
        select(WorkflowStep).where(
            and_(
                WorkflowStep.agreement_id == step.agreement_id,
                WorkflowStep.step_order == step.step_order - 1,
                chain_filter,
            )
        )
    )
    prev_step = prev_res.scalar_one_or_none()
    return prev_step is None or prev_step.status == WorkflowStepStatusEnum.approved


async def _notify_project_users(
    db: AsyncSession,
    agreement: Agreement,
    subject: str,
    body: str,
    exclude_user_id=None,
) -> None:
    """Email all users assigned to the agreement's project (project_users table).

    Falls back to notifying admins if the project has no explicit assignments.
    Failures are swallowed — email is best-effort, never workflow-blocking.
    """
    from models.agreement import ProjectUser

    result = await db.execute(
        select(User)
        .join(ProjectUser, ProjectUser.user_id == User.id)
        .where(
            ProjectUser.project_id == agreement.project_id,
            User.is_active.is_(True),
        )
    )
    users = result.scalars().all()

    if not users:
        # No project assignments — fall back to admins
        result = await db.execute(select(User).where(User.role == RoleEnum.admin, User.is_active.is_(True)))
        users = result.scalars().all()

    seen: set[str] = set()
    for u in users:
        if exclude_user_id and str(u.id) == str(exclude_user_id):
            continue
        if u.email in seen:
            continue
        seen.add(u.email)
        await send_email(to_email=u.email, subject=subject, body=body)


async def _notify_admins_agreement_ready_to_forward(
    db: AsyncSession, agreement: Agreement
) -> None:
    ctx = await _get_email_context(db, agreement)
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
                f"it to the subcontractor.\n\n"
                f"{ctx}"
            ),
        )


async def all_main_steps_approved(db: AsyncSession, agreement_id) -> bool:
    """True when every reviewer role's main-chain step is approved.

    The sequential review chain (Accounts -> PD -> OM -> GM) completes only
    when all four have approved. Resolution steps (a separate sequential
    chain) are excluded.
    """
    res = await db.execute(
        select(WorkflowStep).where(
            and_(
                WorkflowStep.agreement_id == agreement_id,
                ~WorkflowStep.step_name.in_(RESOLUTION_STEP_NAMES),
            )
        )
    )
    steps = res.scalars().all()
    return bool(steps) and all(s.status == WorkflowStepStatusEnum.approved for s in steps)


async def _handle_resolution_approval(
    db: AsyncSession, step: WorkflowStep, agreement: Agreement | None
) -> None:
    """Resolution chain (OM -> GM) stays sequential: notify the next role on
    mid-chain approval, and on the final (GM) approval flag Admin that the
    revised agreement is ready to send back to the subcontractor."""
    last_order = 2
    if step.step_order < last_order:
        next_res = await db.execute(
            select(WorkflowStep).where(
                and_(
                    WorkflowStep.agreement_id == step.agreement_id,
                    WorkflowStep.step_order == step.step_order + 1,
                    WorkflowStep.step_name.in_(RESOLUTION_STEP_NAMES),
                )
            )
        )
        next_step = next_res.scalar_one_or_none()
        if next_step:
            ctx = await _get_email_context(db, agreement) if agreement else ""
            recipients_res = await db.execute(
                select(User).where(User.role == next_step.role_required, User.is_active.is_(True))
            )
            ref = agreement.reference_number if agreement else str(step.agreement_id)
            for recipient in recipients_res.scalars().all():
                await send_email(
                    to_email=recipient.email,
                    subject=f"SAMS Review Required - {ref}",
                    body=(
                        f"Agreement {ref} is pending your review.\n\n"
                        f"Current step: {next_step.step_name}\n\n"
                        f"{ctx}\n\n"
                        "Please log in to SAMS to review and take action."
                    ),
                )
    if agreement and step.step_order == last_order:
        agreement.status_updated_on = datetime.now(UTC)
        await _notify_admins_agreement_ready_to_forward(db, agreement)


async def approve_step(
    db: AsyncSession,
    step: WorkflowStep,
    actor: User,
    comment_text: str | None = None,
    clause_reference: str | None = None,
) -> WorkflowComment | None:
    if not await _previous_step_approved(db, step):
        raise ValueError("The previous reviewer has not approved this agreement yet")

    step.status = WorkflowStepStatusEnum.approved
    step.acted_by = actor.id
    step.acted_at = datetime.now(UTC)

    comment: WorkflowComment | None = None
    if comment_text and comment_text.strip():
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

    if _is_resolution_step(step):
        await _handle_resolution_approval(db, step, agreement)
    elif agreement and await all_main_steps_approved(db, agreement.id):
        agreement.gm_approval_date = date.today()
        agreement.current_status = AgreementStatusEnum.under_internal_review
        agreement.status_updated_on = datetime.now(UTC)
        await _notify_admins_agreement_ready_to_forward(db, agreement)

    if agreement:
        ref = agreement.reference_number
        role_label = step.role_required.value.replace("_", " ").title()
        ctx = await _get_email_context(db, agreement)
        comment_note = f"\n\nComment: {comment.comment_text}" if comment else ""
        await _notify_project_users(
            db, agreement,
            subject=f"SAMS: {role_label} approved {ref}",
            body=(
                f"{actor.name} ({role_label}) has approved agreement {ref}.\n\n"
                f"{ctx}"
                f"{comment_note}\n\n"
                f"Log in to SAMS to view the agreement status."
            ),
            exclude_user_id=actor.id,
        )

    await db.commit()
    if comment:
        await db.refresh(comment)
    return comment


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
        # (Accounts), so any prior approvals on this agreement are wiped.
        agreement.current_status = AgreementStatusEnum.under_bgcc_revision
        agreement.status_updated_on = datetime.now(UTC)

    ctx = await _get_email_context(db, agreement) if agreement else ""
    ref = agreement.reference_number if agreement else str(step.agreement_id)
    admin_result = await db.execute(select(User).where(User.role == RoleEnum.admin, User.is_active.is_(True)))
    admin_users = admin_result.scalars().all()
    for admin in admin_users:
        await send_email(
            to_email=admin.email,
            subject=f"SAMS Return Notice - {ref}",
            body=(
                f"Agreement {ref} has been returned.\n\n"
                f"{ctx}\n\n"
                f"Returned by:     {actor.name}\n"
                f"Step:            {step.step_name}\n"
                f"Clause Ref:      {clause_reference or 'N/A'}\n"
                f"Comment:         {comment.comment_text}"
            ),
        )

    await db.commit()
    await db.refresh(comment)
    return comment


async def add_comment(
    db: AsyncSession,
    step: WorkflowStep,
    actor: User,
    comment_text: str,
    clause_reference: str | None = None,
) -> WorkflowComment:
    """Flat-model review comment — NON-blocking.

    Records a comment against the reviewer's step so it's visible to every
    role, but deliberately does NOT touch the step status or the agreement
    status. The reviewer can still approve later, no chain restart is
    triggered, and other reviewers can approve in parallel. Admin is notified
    so they can resolve the comment.
    """
    if not comment_text.strip():
        raise ValueError("comment_text cannot be empty")

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
        ref = agreement.reference_number
        role_label = step.role_required.value.replace("_", " ").title()
        clause_note = f"\nClause Reference: {clause_reference}" if clause_reference else ""
        ctx = await _get_email_context(db, agreement)
        await _notify_project_users(
            db, agreement,
            subject=f"SAMS: New comment on {ref}",
            body=(
                f"{actor.name} ({role_label}) added a comment on agreement {ref}:\n\n"
                f"{ctx}\n\n"
                f"Comment: {comment.comment_text}{clause_note}\n\n"
                f"Log in to SAMS to view the full review."
            ),
            exclude_user_id=actor.id,
        )

    await db.commit()
    await db.refresh(comment)
    return comment


async def resubmit_agreement(db: AsyncSession, agreement: Agreement) -> None:
    # Spec: resubmit restarts the WHOLE chain from step 1 (Accounts for the
    # main chain, Resolution-OM for the resolution chain) rather than just
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

    # Notify all reviewer roles that the agreement has been resubmitted
    try:
        ctx = await _get_email_context(db, agreement)
        ref = agreement.reference_number or str(agreement.id)
        subject = f"Agreement Resubmitted for Review — {ref}"
        body = (
            f"The agreement '{ref}' has been resubmitted by the Admin after editing.\n\n"
            f"{ctx}\n\n"
            "Please log in to SAMS to review the updated agreement."
        )
        await _notify_project_users(db, agreement, subject, body)
    except Exception:  # noqa: BLE001
        pass


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
        .options(
            selectinload(WorkflowComment.original_author),
            selectinload(WorkflowComment.reactions).selectinload(CommentReaction.reactor),
        )
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
                "author_name": c.original_author.name if c.original_author else None,
                "author_role": c.original_author.role.value if c.original_author else None,
                "reactions": [
                    {
                        "reactor_name": r.reactor.name if r.reactor else None,
                        "reactor_role": r.reactor_role,
                        "reaction": r.reaction,
                    }
                    for r in (c.reactions or [])
                ],
            }
            for c in comments
        ],
    }
