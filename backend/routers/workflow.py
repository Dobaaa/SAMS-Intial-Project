import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from middleware.rbac import get_current_user
from models.user import User
from models.workflow import WorkflowStep
from services.workflow_engine import (
    add_comment,
    approve_step,
    get_all_for_role,
    get_pending_for_role,
    get_workflow_agreement_summary,
    return_step,
)

router = APIRouter(prefix="/workflow", tags=["workflow"])


class ReturnPayload(BaseModel):
    comment_text: str
    clause_reference: str | None = None


@router.get("/pending")
async def get_pending_workflows(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return await get_pending_for_role(db, current_user.role)


@router.get("/my-agreements")
async def get_my_agreements(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """All steps (pending + approved + returned) for this reviewer's role,
    with enriched agreement info. Used by the sidebar and reviewer dashboard
    so agreements remain visible after approval."""
    return await get_all_for_role(db, current_user.role)


@router.post("/{step_id}/approve")
async def approve_workflow_step(
    step_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    step_res = await db.execute(select(WorkflowStep).where(WorkflowStep.id == step_id))
    step = step_res.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow step not found")
    if step.role_required != current_user.role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed for this role")
    await approve_step(db, step, current_user)
    return {"status": "approved"}


@router.post("/{step_id}/comment")
async def comment_workflow_step(
    step_id: uuid.UUID,
    payload: ReturnPayload,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Flat-model review comment: non-blocking. The reviewer for this step
    records a comment visible to all roles without approving and without
    bouncing the agreement back to Admin."""
    step_res = await db.execute(select(WorkflowStep).where(WorkflowStep.id == step_id))
    step = step_res.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow step not found")
    if step.role_required != current_user.role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed for this role")

    try:
        comment = await add_comment(db, step, current_user, payload.comment_text, payload.clause_reference)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "commented", "comment_id": str(comment.id)}


@router.post("/{step_id}/return")
async def return_workflow_step(
    step_id: uuid.UUID,
    payload: ReturnPayload,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    step_res = await db.execute(select(WorkflowStep).where(WorkflowStep.id == step_id))
    step = step_res.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow step not found")
    if step.role_required != current_user.role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed for this role")

    try:
        comment = await return_step(db, step, current_user, payload.comment_text, payload.clause_reference)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "returned", "comment_id": str(comment.id)}


@router.get("/agreements/{agreement_id}")
async def get_workflow_agreement(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> dict:
    data = await get_workflow_agreement_summary(db, str(agreement_id))
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")
    return data


@router.get("/agreements/{agreement_id}/fields")
async def get_workflow_agreement_fields(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> dict:
    """Field matrix for the clause review tab.

    Returns all Form + Conditions master fields with their default values and
    the current agreement values, so every reviewer can see original vs amended
    side-by-side. Appendix fields are excluded (they are derived, not clauses).
    Accessible to any authenticated user (reviewer roles need this view).
    """
    from models.agreement import Agreement, AgreementFieldValue
    from models.master import MasterField

    agreement_res = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    agreement = agreement_res.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")

    template_ids = [
        v for v in [agreement.form_version_id, agreement.conditions_version_id] if v
    ]
    field_res = await db.execute(
        select(MasterField)
        .where(MasterField.template_id.in_(template_ids))
        .order_by(MasterField.sort_order.asc())
    )
    master_fields = field_res.scalars().all()

    value_res = await db.execute(
        select(AgreementFieldValue).where(AgreementFieldValue.agreement_id == agreement.id)
    )
    values = {r.field_id: (r.entered_value or "") for r in value_res.scalars().all()}

    return {
        "fields": [
            {
                "field_id": f.field_id,
                "field_label": f.field_label,
                "clause_number": f.clause_number or "",
                "input_type": f.input_type.value,
                "default_value": f.default_value or "",
                "current_value": values.get(f.field_id, ""),
            }
            for f in master_fields
        ]
    }


@router.get("/agreements/{agreement_id}/appendix-fields")
async def get_workflow_agreement_appendix_fields(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> dict:
    """Appendix field matrix for the appendix review tab.

    Returns appendix rows (A01–A23, filtered by show_in_appendix) plus C15
    Optional Terms appended at the end, each with the master default value
    (original) and the current agreement value. Accessible to any authenticated
    user.
    """
    from models.agreement import Agreement, AgreementFieldValue, AppendixConfig
    from models.master import MasterField

    agreement_res = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    agreement = agreement_res.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")

    config_res = await db.execute(
        select(AppendixConfig)
        .where(AppendixConfig.agreement_id == agreement_id)
        .order_by(AppendixConfig.sort_order.asc())
    )
    configs = config_res.scalars().all()

    master_res = await db.execute(select(MasterField))
    master_map = {mf.field_id: mf for mf in master_res.scalars().all()}

    value_res = await db.execute(
        select(AgreementFieldValue).where(AgreementFieldValue.agreement_id == agreement.id)
    )
    value_map = {v.field_id: (v.entered_value or "") for v in value_res.scalars().all()}

    rows: list[dict] = []
    for cfg in configs:
        mf = master_map.get(cfg.field_id)
        if not mf or not cfg.show_in_appendix:
            continue
        rows.append({
            "field_id": cfg.field_id,
            "row_label": mf.appendix_row_label or mf.field_label,
            "clause_ref": mf.appendix_clause_ref or mf.clause_number or "",
            "default_value": mf.default_value or "",
            "current_value": value_map.get(cfg.field_id, ""),
            "auto_source_field_id": mf.auto_source_field_id,
        })

    # Append C15 "Optional Terms" — a Conditions field shown as the last appendix row
    c15 = master_map.get("C15")
    if c15:
        rows.append({
            "field_id": "C15",
            "row_label": c15.appendix_row_label or "Optional Terms",
            "clause_ref": c15.appendix_clause_ref or "",
            "default_value": c15.default_value or "",
            "current_value": value_map.get("C15", ""),
            "auto_source_field_id": None,
        })

    return {"fields": rows}
