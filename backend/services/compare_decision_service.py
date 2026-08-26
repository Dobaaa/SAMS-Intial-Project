"""Per-row decisions on the GM Compare table (2026-08-26 client feedback:
"a decision action for every change ... not for all the changes"). Every
row (a filled-in field value, or a formal clause revision) gets its own
Approve / Approve with comments / Reject with comments decision; the
agreement's overall workflow step only resolves once every row has one.

Clause-revision rows reuse the existing, unmodified accept/reject endpoints
in routers/clause_revisions.py (accept_revision/reject_revision) — this
module only adds the missing half: decisions on plain field-value rows
(AgreementFieldReview, new), plus the shared "is everything decided yet,
and if so what's the aggregate outcome" check that both row kinds feed
into via the finalize-check endpoint.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.agreement import (
    AgreementClauseRevision,
    AgreementFieldReview,
    AgreementFieldValue,
    ClauseRevisionStatus,
    FieldReviewStatus,
)
from models.master import MasterField, MasterTemplate
from models.user import User
from models.workflow import WorkflowStep, WorkflowStepStatusEnum
from services.audit_service import record_audit
from services.workflow_engine import _previous_step_approved, approve_step, return_step


async def _active_field_catalog(db: AsyncSession) -> dict[str, MasterField]:
    """field_id -> MasterField, across the active Form/Conditions/Appendix
    templates. Gives compare-table field-value rows a clause number, label,
    and the master's own default/placeholder text (usually "[Insert]")."""
    templates_res = await db.execute(select(MasterTemplate).where(MasterTemplate.is_active.is_(True)))
    template_ids = [t.id for t in templates_res.scalars().all()]
    if not template_ids:
        return {}
    fields_res = await db.execute(select(MasterField).where(MasterField.template_id.in_(template_ids)))
    return {f.field_id: f for f in fields_res.scalars().all()}


async def get_actor_actionable_step(
    db: AsyncSession, agreement_id: uuid.UUID, user: User
) -> WorkflowStep | None:
    """The user's own WorkflowStep on this agreement, if they currently have
    one that's pending AND chain-unlocked (the same "is it actually your
    turn" gate the rest of the workflow uses)."""
    res = await db.execute(
        select(WorkflowStep).where(
            WorkflowStep.agreement_id == agreement_id,
            WorkflowStep.role_required == user.role,
            WorkflowStep.status == WorkflowStepStatusEnum.pending,
        )
    )
    step = res.scalar_one_or_none()
    if step is None:
        return None
    if not await _previous_step_approved(db, step):
        return None
    return step


async def _row_identities(
    db: AsyncSession, agreement_id: uuid.UUID
) -> tuple[list[uuid.UUID], list[str]]:
    """Every row id currently on this agreement's compare table, split by
    kind — the same set build_compare_rows shows, so the finalize check and
    the GET endpoint can never drift apart."""
    rev_res = await db.execute(
        select(AgreementClauseRevision.id).where(AgreementClauseRevision.agreement_id == agreement_id)
    )
    clause_revision_ids = list(rev_res.scalars().all())

    catalog = await _active_field_catalog(db)
    fv_res = await db.execute(
        select(AgreementFieldValue).where(AgreementFieldValue.agreement_id == agreement_id)
    )
    field_ids = [
        fv.field_id
        for fv in fv_res.scalars().all()
        if (fv.entered_value or "").strip() and fv.field_id in catalog
    ]
    return clause_revision_ids, field_ids


async def build_compare_rows(
    db: AsyncSession, agreement_id: uuid.UUID, viewer_step: WorkflowStep | None
) -> list[dict]:
    """Row-building logic for GET .../compare-table, extended with each
    row's decision_status/decision_comment/decided_by_name — computed
    against the VIEWER's own actionable step. With no actionable step
    (nothing pending for them, or an observer role), every row just reads
    "pending" with no comment — matches canDecide being false client-side,
    so no action buttons render anyway."""
    rev_res = await db.execute(
        select(AgreementClauseRevision)
        .where(AgreementClauseRevision.agreement_id == agreement_id)
        .options(selectinload(AgreementClauseRevision.created_by_user), selectinload(AgreementClauseRevision.decided_by_user))
        .order_by(AgreementClauseRevision.created_at.asc())
    )
    revisions = rev_res.scalars().all()

    # Clause-revision decisions aren't scoped per workflow step (pre-existing
    # design, unrelated to this feature) — whatever the row's own status/
    # decided_by already says applies regardless of who's viewing.
    CLAUSE_STATUS_MAP = {
        ClauseRevisionStatus.pending.value: "pending",
        ClauseRevisionStatus.accepted.value: "approved",
        ClauseRevisionStatus.rejected.value: "rejected",
    }
    rows = [
        {
            "id": str(rev.id),
            "kind": "clause_revision",
            "field_id": None,
            "clause_label": rev.clause_label,
            "original_text": rev.original_text,
            "revised_text": rev.modified_text,
            "change_reason": rev.change_reason,
            "status": rev.status,
            "decision_status": CLAUSE_STATUS_MAP.get(rev.status, rev.status),
            "decision_comment": rev.decision_note,
            "decided_by_name": rev.decided_by_user.name if rev.decided_by_user else None,
            "generated_by_name": rev.created_by_user.name if rev.created_by_user else None,
            "generated_by_role": rev.created_by_user.role.value if rev.created_by_user else None,
            "created_at": rev.created_at.isoformat() if rev.created_at else None,
        }
        for rev in revisions
    ]

    catalog = await _active_field_catalog(db)
    fv_res = await db.execute(
        select(AgreementFieldValue)
        .where(AgreementFieldValue.agreement_id == agreement_id)
        .options(selectinload(AgreementFieldValue.entered_by_user))
    )
    field_values = fv_res.scalars().all()

    field_reviews: dict[str, AgreementFieldReview] = {}
    if viewer_step is not None:
        fr_res = await db.execute(
            select(AgreementFieldReview)
            .where(AgreementFieldReview.workflow_step_id == viewer_step.id)
            .options(selectinload(AgreementFieldReview.decided_by_user))
        )
        field_reviews = {fr.field_id: fr for fr in fr_res.scalars().all()}

    field_rows: list[tuple[tuple[str, int], dict]] = []
    for fv in field_values:
        value = (fv.entered_value or "").strip()
        field = catalog.get(fv.field_id)
        if not value or field is None:
            continue
        label = f"{field.clause_number} — {field.field_label}" if field.clause_number else field.field_label
        review = field_reviews.get(fv.field_id)
        field_rows.append((
            (fv.field_id[0], field.sort_order),
            {
                "id": f"field-{fv.id}",
                "kind": "field",
                "field_id": fv.field_id,
                "clause_label": label,
                "original_text": field.default_value or "[Insert]",
                "revised_text": value,
                "change_reason": None,
                "status": "entered",
                "decision_status": review.status if review else FieldReviewStatus.pending.value,
                "decision_comment": review.comment_text if review else None,
                "decided_by_name": review.decided_by_user.name if review and review.decided_by_user else None,
                "generated_by_name": fv.entered_by_user.name if fv.entered_by_user else None,
                "generated_by_role": fv.entered_by_user.role.value if fv.entered_by_user else None,
                "created_at": fv.entered_at.isoformat() if fv.entered_at else None,
            },
        ))
    field_rows.sort(key=lambda item: item[0])
    rows.extend(row for _, row in field_rows)

    return rows


async def record_field_decision(
    db: AsyncSession,
    agreement_id: uuid.UUID,
    field_id: str,
    decision: str,
    comment_text: str | None,
    actor: User,
) -> AgreementFieldReview:
    step = await get_actor_actionable_step(db, agreement_id, actor)
    if step is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have no actionable review step on this agreement",
        )

    if decision not in (FieldReviewStatus.approved.value, FieldReviewStatus.rejected.value):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="decision must be 'approved' or 'rejected'")

    _, valid_field_ids = await _row_identities(db, agreement_id)
    if field_id not in valid_field_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found on this agreement's compare table")

    if decision == FieldReviewStatus.rejected.value and not (comment_text or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A comment is required to reject")

    res = await db.execute(
        select(AgreementFieldReview).where(
            AgreementFieldReview.workflow_step_id == step.id,
            AgreementFieldReview.field_id == field_id,
        )
    )
    review = res.scalar_one_or_none()
    if review is None:
        review = AgreementFieldReview(
            agreement_id=agreement_id,
            workflow_step_id=step.id,
            field_id=field_id,
        )
        db.add(review)

    review.status = decision
    review.comment_text = (comment_text or "").strip() or None
    review.decided_by = actor.id
    review.decided_at = datetime.now(UTC)

    await db.flush()
    await record_audit(
        db,
        actor_id=actor.id,
        action=f"field_review.{decision}",
        entity_type="agreement_field_review",
        entity_id=review.id,
        new_value={"field_id": field_id, "agreement_id": str(agreement_id), "comment_text": review.comment_text},
    )
    await db.commit()
    await db.refresh(review)
    return review


async def check_and_finalize_step(db: AsyncSession, agreement_id: uuid.UUID, actor: User) -> dict:
    """Once every row on the agreement has a decision (by the actor's own
    review step), resolve the step: any rejection returns the agreement to
    Admin (via return_step); all-approved approves the step (via
    approve_step). Both are reused as black boxes so their existing side
    effects (emails, gm_approval_date, resolution-chain branching) keep
    working unmodified. No-op (not an error) if the actor has nothing
    actionable, or if anything is still undecided."""
    step = await get_actor_actionable_step(db, agreement_id, actor)
    if step is None:
        return {"step_finalized": False}

    clause_ids, field_ids = await _row_identities(db, agreement_id)
    if not clause_ids and not field_ids:
        # Nothing to review — never silently auto-approve an empty agreement.
        return {"step_finalized": False}

    revisions: list[AgreementClauseRevision] = []
    if clause_ids:
        rev_res = await db.execute(
            select(AgreementClauseRevision).where(AgreementClauseRevision.id.in_(clause_ids))
        )
        revisions = list(rev_res.scalars().all())
    if any(rev.status == ClauseRevisionStatus.pending.value for rev in revisions):
        return {"step_finalized": False}

    field_reviews: dict[str, AgreementFieldReview] = {}
    if field_ids:
        fr_res = await db.execute(
            select(AgreementFieldReview).where(
                AgreementFieldReview.workflow_step_id == step.id,
                AgreementFieldReview.field_id.in_(field_ids),
            )
        )
        field_reviews = {fr.field_id: fr for fr in fr_res.scalars().all()}
    if any(fid not in field_reviews or field_reviews[fid].status == FieldReviewStatus.pending.value for fid in field_ids):
        return {"step_finalized": False}

    rejected_items: list[str] = []
    approved_comments: list[str] = []

    for rev in revisions:
        if rev.status == ClauseRevisionStatus.rejected.value:
            rejected_items.append(f"{rev.clause_label}: {rev.decision_note or '(no comment)'}")
        elif rev.decision_note:
            approved_comments.append(f"{rev.clause_label}: {rev.decision_note}")

    catalog = await _active_field_catalog(db)
    for fid in field_ids:
        review = field_reviews[fid]
        field = catalog.get(fid)
        label = field.field_label if field else fid
        if review.status == FieldReviewStatus.rejected.value:
            rejected_items.append(f"{label}: {review.comment_text or '(no comment)'}")
        elif review.comment_text:
            approved_comments.append(f"{label}: {review.comment_text}")

    try:
        if rejected_items:
            aggregated = "Rejected via Compare page:\n" + "\n".join(f"- {item}" for item in rejected_items)
            await return_step(db, step, actor, comment_text=aggregated)
            return {"step_finalized": True, "step_result": "returned"}

        aggregated = (
            "Approved with comments via Compare page:\n" + "\n".join(f"- {item}" for item in approved_comments)
            if approved_comments
            else None
        )
        await approve_step(db, step, actor, comment_text=aggregated)
        return {"step_finalized": True, "step_result": "approved"}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
