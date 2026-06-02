import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from middleware.rbac import get_current_user
from models.agreement import Agreement
from models.user import User
from services.ai_service import (
    AIProviderError,
    check_grammar_wording,
    compare_clauses,
    detect_risks,
    generate_summary,
    suggest_responses,
    validate_revision,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/{agreement_id}/analyze")
async def analyze_agreement(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> dict:
    agreement = await db.get(Agreement, agreement_id)
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")

    try:
        comparison = await compare_clauses(db, str(agreement_id))
        risks = await detect_risks(db, str(agreement_id))
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "status": "success",
        "data": {
            "comparison": comparison.data,
            "risks": risks.data,
        },
        "cached": comparison.cached and risks.cached,
    }


@router.get("/{agreement_id}/summary")
async def get_summary(
    agreement_id: uuid.UUID,
    role: str = Query(default="gm"),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> dict:
    agreement = await db.get(Agreement, agreement_id)
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    try:
        result = await generate_summary(db, str(agreement_id), role)
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": result.data, "cached": result.cached}


@router.post("/resolution/{agreement_id}/suggest")
async def suggest_resolution_responses(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = await suggest_responses(db, str(agreement_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": result.data, "cached": result.cached}


@router.post("/{agreement_id}/grammar")
async def check_grammar(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> dict:
    agreement = await db.get(Agreement, agreement_id)
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    try:
        result = await check_grammar_wording(db, str(agreement_id))
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": result.data, "cached": result.cached}


@router.post("/{agreement_id}/validate-revision")
async def validate_agreement_revision(
    agreement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> dict:
    agreement = await db.get(Agreement, agreement_id)
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    try:
        result = await validate_revision(db, str(agreement_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": result.data, "cached": result.cached}
