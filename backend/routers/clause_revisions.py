"""Clause revision endpoints (Phase 4 v2).

  GET    /api/agreements/{id}/clauses
      List the revisable paragraphs in the master docx (deduped, sorted in
      document order). Used by the Document view's clause picker.

  GET    /api/agreements/{id}/revisions
      Every clause revision this agreement carries (any status).

  POST   /api/agreements/{id}/revisions
      Create a new revision (status=pending). Admin only — reviewers
      accept/reject in v2.1.

  PATCH  /api/agreements/{id}/revisions/{rev_id}
      Update the modified_text or change_reason while still pending.

  DELETE /api/agreements/{id}/revisions/{rev_id}
      Withdraw a pending revision. Accepted/rejected revisions are
      historical and cannot be deleted (they show up in the audit trail).

  GET    /api/agreements/{id}/compare-table
      Per-row Compare view (GM Portal) — every filled field value plus any
      clause revisions, each with its own decision_status.

  POST   /api/agreements/{id}/compare-table/fields/{field_id}/decision
      Approve or reject one field-value row. See services/compare_decision_service.

  POST   /api/agreements/{id}/compare-table/finalize-check
      Called after every row decision; resolves the actor's workflow step
      once every row is decided.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import UTC, datetime

from database import get_db_session
from middleware.rbac import get_current_user, require_role
from models.agreement import Agreement, AgreementClauseRevision, ClauseRevisionStatus
from models.user import RoleEnum, User
from services.audit_service import record_audit
from services.clause_revision_service import (
    find_master_clause_by_hash,
    list_master_clauses,
)
from services.workflow_engine import notify_already_approved_reviewers
from services.compare_decision_service import (
    build_compare_rows,
    check_and_finalize_step,
    record_field_decision,
)

# Reviewer roles allowed to accept or reject a clause revision (Rev 01 item
# 17-extension: "THIS TRACKING WILL APPLY TO GM-PD-OM-ACCOUNTS-ADMIN").
# Admin is included so the same person who created a revision can withdraw
# decisions during the drafting phase via DELETE, but cannot self-accept
# (see _ensure_can_decide below).
REVIEWER_ROLES = (
    RoleEnum.admin,
    RoleEnum.project_director,
    RoleEnum.accounts,
    RoleEnum.operation_manager,
    RoleEnum.gm,
)

router = APIRouter(tags=["clause-revisions"])


# ---------- payload models ----------------------------------------------------


class RevisionCreatePayload(BaseModel):
    clause_hash: str = Field(..., min_length=64, max_length=64)
    modified_text: str
    change_reason: str | None = None


class RevisionUpdatePayload(BaseModel):
    modified_text: str | None = None
    change_reason: str | None = None


class RevisionDecisionPayload(BaseModel):
    decision_note: str | None = None


# ---------- helpers -----------------------------------------------------------


async def _get_agreement_or_404(db: AsyncSession, agreement_id: uuid.UUID) -> Agreement:
    res = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    agreement = res.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")
    if agreement.is_executed:
        # Executed agreements are immutable — no new revisions, no edits.
        # We still allow GET on the list so the executed PDF can show prior
        # revisions for the audit trail.
        pass
    return agreement


def _serialise(rev: AgreementClauseRevision) -> dict:
    return {
        "id": str(rev.id),
        "agreement_id": str(rev.agreement_id),
        "clause_hash": rev.clause_hash,
        "clause_label": rev.clause_label,
        "original_text": rev.original_text,
        "modified_text": rev.modified_text,
        "change_reason": rev.change_reason,
        "status": rev.status,
        "created_by": str(rev.created_by) if rev.created_by else None,
        "created_at": rev.created_at.isoformat() if rev.created_at else None,
        "decided_by": str(rev.decided_by) if rev.decided_by else None,
        "decided_at": rev.decided_at.isoformat() if rev.decided_at else None,
        "decision_note": rev.decision_note,
    }


# ---------- routes ------------------------------------------------------------


@router.get("/agreements/{agreement_id}/clauses")
async def list_clauses(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> dict:
    """Return the master clause catalog, plus any pending revisions on this
    agreement so the UI can show which clauses already have an open edit."""
    await _get_agreement_or_404(db, agreement_id)

    clauses = [c.as_dict() for c in list_master_clauses()]

    rev_res = await db.execute(
        select(AgreementClauseRevision).where(
            AgreementClauseRevision.agreement_id == agreement_id
        )
    )
    revisions = rev_res.scalars().all()
    pending_hashes = {r.clause_hash for r in revisions if r.status == ClauseRevisionStatus.pending.value}
    accepted_hashes = {r.clause_hash for r in revisions if r.status == ClauseRevisionStatus.accepted.value}

    for clause in clauses:
        clause["has_pending"] = clause["clause_hash"] in pending_hashes
        clause["has_accepted"] = clause["clause_hash"] in accepted_hashes

    return {"clauses": clauses}


@router.get("/agreements/{agreement_id}/revisions")
async def list_revisions(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> dict:
    await _get_agreement_or_404(db, agreement_id)
    res = await db.execute(
        select(AgreementClauseRevision)
        .where(AgreementClauseRevision.agreement_id == agreement_id)
        .order_by(AgreementClauseRevision.created_at.desc())
    )
    return {"revisions": [_serialise(r) for r in res.scalars().all()]}


@router.get("/agreements/{agreement_id}/compare-table")
async def get_compare_table(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Simple table Compare view for the GM Portal: Original Agreement /
    Revised Agreement with Amendment / Generated by Whom. Read-only — GM's
    actual decision is one overall Approve / Approved with comments /
    Rejected with comments at the bottom of the page (plain
    /workflow/{step}/approve|return, not row-specific).

    Two row sources:
      - Formal clause revisions (agreement_clause_revisions) — always shown,
        every one exists because Admin deliberately proposed it.
      - Filled-in field values (F/C/A) — shown ONLY when a non-admin
        reviewer (Accounts/PD/OM) left a comment referencing that field.
        Everything else Admin entered is noise GM doesn't need to see
        item-by-item; see services/compare_decision_service.build_compare_rows.
    """
    await _get_agreement_or_404(db, agreement_id)
    rows = await build_compare_rows(db, agreement_id, viewer_role=current_user.role)
    return {"rows": rows}


class FieldDecisionPayload(BaseModel):
    decision: str
    comment_text: str | None = None


@router.post("/agreements/{agreement_id}/compare-table/fields/{field_id}/decision")
async def decide_field_row(
    agreement_id: uuid.UUID,
    field_id: str,
    payload: FieldDecisionPayload,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Per-row decision on a "field" compare-table row — the counterpart to
    /revisions/{id}/accept|reject for "clause_revision" rows, which already
    exist below and are untouched by this feature."""
    await _get_agreement_or_404(db, agreement_id)
    review = await record_field_decision(
        db, agreement_id, field_id, payload.decision, payload.comment_text, current_user
    )
    return {"status": "success", "decision_status": review.status, "field_id": field_id}


@router.post("/agreements/{agreement_id}/compare-table/finalize-check")
async def finalize_compare_table(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Called by the Compare page after every row decision (field or clause
    revision). No-op unless every row on the agreement now has a decision,
    in which case it resolves the actor's workflow step (approve or return)
    based on the aggregate — see check_and_finalize_step."""
    await _get_agreement_or_404(db, agreement_id)
    return await check_and_finalize_step(db, agreement_id, current_user)


@router.post(
    "/agreements/{agreement_id}/revisions",
    dependencies=[Depends(require_role(RoleEnum.admin))],
)
async def create_revision(
    agreement_id: uuid.UUID,
    payload: RevisionCreatePayload,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_role(RoleEnum.admin)),
) -> dict:
    agreement = await _get_agreement_or_404(db, agreement_id)
    if agreement.is_executed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agreement is locked after execution",
        )

    clause = find_master_clause_by_hash(payload.clause_hash)
    if clause is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clause not found in master template",
        )
    if payload.modified_text.strip() == clause.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Modified text is identical to the original",
        )

    revision = AgreementClauseRevision(
        agreement_id=agreement_id,
        clause_hash=clause.clause_hash,
        clause_label=clause.clause_label,
        original_text=clause.text,
        modified_text=payload.modified_text,
        change_reason=payload.change_reason,
        status=ClauseRevisionStatus.pending.value,
        created_by=current_user.id,
    )
    db.add(revision)
    # Bumps agreement.updated_at so the "modified since your approval" UI
    # flag (derived from this timestamp vs each step's acted_at) also
    # catches a clause-revision-only change, not just plain field edits.
    agreement.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(revision)

    await notify_already_approved_reviewers(
        db,
        agreement,
        current_user,
        change_summary=f"{revision.clause_label} (proposed clause edit)",
        changed_field_ids=["CLAUSE"],
    )

    return _serialise(revision)


@router.patch(
    "/agreements/{agreement_id}/revisions/{revision_id}",
    dependencies=[Depends(require_role(RoleEnum.admin))],
)
async def update_revision(
    agreement_id: uuid.UUID,
    revision_id: uuid.UUID,
    payload: RevisionUpdatePayload,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_role(RoleEnum.admin)),
) -> dict:
    res = await db.execute(
        select(AgreementClauseRevision).where(
            AgreementClauseRevision.id == revision_id,
            AgreementClauseRevision.agreement_id == agreement_id,
        )
    )
    rev = res.scalar_one_or_none()
    if rev is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")
    if rev.status != ClauseRevisionStatus.pending.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending revisions can be edited",
        )
    if payload.modified_text is not None:
        rev.modified_text = payload.modified_text
    if payload.change_reason is not None:
        rev.change_reason = payload.change_reason
    await db.commit()
    await db.refresh(rev)
    return _serialise(rev)


async def _load_pending_revision(
    db: AsyncSession,
    agreement_id: uuid.UUID,
    revision_id: uuid.UUID,
) -> AgreementClauseRevision:
    res = await db.execute(
        select(AgreementClauseRevision).where(
            AgreementClauseRevision.id == revision_id,
            AgreementClauseRevision.agreement_id == agreement_id,
        )
    )
    rev = res.scalar_one_or_none()
    if rev is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")
    if rev.status != ClauseRevisionStatus.pending.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Revision is already {rev.status}",
        )
    return rev


def _ensure_can_decide(rev: AgreementClauseRevision, user: User) -> None:
    """Reviewer-of-clause-revisions check. Anyone in REVIEWER_ROLES can
    decide, EXCEPT the user who created the revision — segregation of
    duties so admin can't rubber-stamp their own edits."""
    if user.role not in REVIEWER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role cannot accept or reject clause revisions",
        )
    if rev.created_by == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot accept or reject a revision you created (withdraw it via DELETE instead)",
        )


@router.post("/agreements/{agreement_id}/revisions/{revision_id}/accept")
async def accept_revision(
    agreement_id: uuid.UUID,
    revision_id: uuid.UUID,
    payload: RevisionDecisionPayload | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Mark a pending revision as accepted. Applied to subsequent PDF
    renders of this agreement only (the master template is untouched)."""
    await _get_agreement_or_404(db, agreement_id)
    rev = await _load_pending_revision(db, agreement_id, revision_id)
    _ensure_can_decide(rev, current_user)

    rev.status = ClauseRevisionStatus.accepted.value
    rev.decided_by = current_user.id
    rev.decided_at = datetime.now(UTC)
    rev.decision_note = (payload.decision_note if payload else None)

    await record_audit(
        db,
        actor_id=current_user.id,
        action="clause_revision.accepted",
        entity_type="agreement_clause_revision",
        entity_id=rev.id,
        new_value={
            "clause_label": rev.clause_label,
            "agreement_id": str(agreement_id),
            "decision_note": rev.decision_note,
        },
    )
    await db.commit()
    await db.refresh(rev)
    return _serialise(rev)


@router.post("/agreements/{agreement_id}/revisions/{revision_id}/reject")
async def reject_revision(
    agreement_id: uuid.UUID,
    revision_id: uuid.UUID,
    payload: RevisionDecisionPayload | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Mark a pending revision as rejected. The original master text stays
    canonical; rejected revision is preserved for the audit trail."""
    await _get_agreement_or_404(db, agreement_id)
    rev = await _load_pending_revision(db, agreement_id, revision_id)
    _ensure_can_decide(rev, current_user)

    rev.status = ClauseRevisionStatus.rejected.value
    rev.decided_by = current_user.id
    rev.decided_at = datetime.now(UTC)
    rev.decision_note = (payload.decision_note if payload else None)

    await record_audit(
        db,
        actor_id=current_user.id,
        action="clause_revision.rejected",
        entity_type="agreement_clause_revision",
        entity_id=rev.id,
        new_value={
            "clause_label": rev.clause_label,
            "agreement_id": str(agreement_id),
            "decision_note": rev.decision_note,
        },
    )
    await db.commit()
    await db.refresh(rev)
    return _serialise(rev)


@router.delete(
    "/agreements/{agreement_id}/revisions/{revision_id}",
    dependencies=[Depends(require_role(RoleEnum.admin))],
)
async def delete_revision(
    agreement_id: uuid.UUID,
    revision_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_role(RoleEnum.admin)),
) -> dict:
    res = await db.execute(
        select(AgreementClauseRevision).where(
            AgreementClauseRevision.id == revision_id,
            AgreementClauseRevision.agreement_id == agreement_id,
        )
    )
    rev = res.scalar_one_or_none()
    if rev is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")
    if rev.status != ClauseRevisionStatus.pending.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Accepted / rejected revisions cannot be deleted",
        )
    await db.delete(rev)
    await db.commit()
    return {"status": "deleted", "id": str(revision_id)}
