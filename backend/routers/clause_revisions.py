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
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
    _: User = Depends(get_current_user),
) -> dict:
    """Simple 3-column Compare view for the GM Portal (req 6.4): Original
    Agreement / Revised Agreement with Amendment / Generated by Whom.

    Every clause revision on this agreement is inherently "an important
    admin-entered clause" — a revision only exists because Admin
    deliberately proposed changing specific legal text — so no separate
    allowlist/importance flag is needed; this is a straight reshape of the
    same agreement_clause_revisions rows list_revisions() already exposes,
    unlike the existing AgreementCompare.tsx/ClauseRevisionsPanel.tsx
    inline track-changes view which this does not touch.
    """
    await _get_agreement_or_404(db, agreement_id)
    res = await db.execute(
        select(AgreementClauseRevision)
        .where(AgreementClauseRevision.agreement_id == agreement_id)
        .options(selectinload(AgreementClauseRevision.created_by_user))
        .order_by(AgreementClauseRevision.created_at.asc())
    )
    rows = [
        {
            "id": str(rev.id),
            "clause_label": rev.clause_label,
            "original_text": rev.original_text,
            "revised_text": rev.modified_text,
            "change_reason": rev.change_reason,
            "status": rev.status,
            "generated_by_name": rev.created_by_user.name if rev.created_by_user else None,
            "generated_by_role": rev.created_by_user.role.value if rev.created_by_user else None,
            "created_at": rev.created_at.isoformat() if rev.created_at else None,
        }
        for rev in res.scalars().all()
    ]
    return {"rows": rows}


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
    await db.commit()
    await db.refresh(revision)
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
