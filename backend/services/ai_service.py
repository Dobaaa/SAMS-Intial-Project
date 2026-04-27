from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import logging

import redis.asyncio as redis
from openai import APIError, APIConnectionError, AsyncOpenAI, AuthenticationError, RateLimitError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)


class AIProviderError(RuntimeError):
    """Raised when the AI provider (Groq/OpenAI) call fails for any reason."""

from config import get_settings
from models.agreement import Agreement, AgreementFieldValue
from models.ai_review import AIReview, DeviationReport, ReviewTypeEnum
from models.master import MasterField
from models.resolution import CommentsResolutionSheet

settings = get_settings()
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
ai_client = AsyncOpenAI(
    api_key=settings.GROQ_API_KEY,
    base_url=settings.AI_BASE_URL,
)
CACHE_TTL_SECONDS = 60 * 60 * 24


@dataclass
class AIResult:
    data: Any
    cached: bool


def _cache_key(agreement_id: str, review_type: str, suffix: str | None = None) -> str:
    base = f"sams:ai:{agreement_id}:{review_type}"
    return f"{base}:{suffix}" if suffix else base


def _extract_json(text: str) -> Any:
    raw = text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    bracket = re.search(r"(\{.*\}|\[.*\])", raw, re.DOTALL)
    if bracket:
        return json.loads(bracket.group(1))
    raise ValueError("AI response is not valid JSON")


async def _chat_json(system_prompt: str, user_prompt: str) -> Any:
    try:
        completion = await ai_client.chat.completions.create(
            model=settings.AI_MODEL,
            temperature=0.1,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except AuthenticationError as exc:
        log.error("AI auth failed: %s", exc)
        raise AIProviderError("AI provider rejected the API key.") from exc
    except RateLimitError as exc:
        log.warning("AI rate limit hit: %s", exc)
        raise AIProviderError("AI provider rate limit reached. Try again shortly.") from exc
    except APIConnectionError as exc:
        log.warning("AI connection error: %s", exc)
        raise AIProviderError("Could not reach AI provider. Check network and try again.") from exc
    except APIError as exc:
        log.error("AI API error: %s", exc)
        raise AIProviderError("AI provider returned an error.") from exc

    content = completion.choices[0].message.content or "[]"
    try:
        return _extract_json(content)
    except (ValueError, json.JSONDecodeError) as exc:
        log.error("AI returned non-JSON content: %r", content[:300])
        raise AIProviderError("AI response was not valid JSON.") from exc


async def _set_cache(key: str, payload: Any) -> None:
    await redis_client.setex(key, CACHE_TTL_SECONDS, json.dumps(payload))


async def _get_cache(key: str) -> Any | None:
    cached = await redis_client.get(key)
    if not cached:
        return None
    return json.loads(cached)


async def _store_ai_review(
    db: AsyncSession,
    agreement_id: str,
    review_type: ReviewTypeEnum,
    findings: Any,
    risk_score: int | None = None,
) -> None:
    db.add(
        AIReview(
            agreement_id=agreement_id,
            review_type=review_type,
            findings_json=findings,
            risk_score=risk_score,
            model_used=settings.AI_MODEL,
        )
    )
    await db.commit()


async def _get_deviation_rows(db: AsyncSession, agreement_id: str) -> list[dict]:
    report_res = await db.execute(
        select(DeviationReport).where(DeviationReport.agreement_id == agreement_id).order_by(DeviationReport.generated_at.desc()).limit(1)
    )
    report = report_res.scalar_one_or_none()
    if report and isinstance(report.report_data_json, list):
        return report.report_data_json

    fields_res = await db.execute(
        select(AgreementFieldValue, MasterField)
        .join(MasterField, MasterField.field_id == AgreementFieldValue.field_id)
        .where(AgreementFieldValue.agreement_id == agreement_id)
    )
    rows: list[dict] = []
    for afv, mf in fields_res.all():
        default = (mf.default_value or "").strip()
        entered = (afv.entered_value or "").strip()
        change_type = "Unchanged"
        if default != entered:
            change_type = "Filled" if (not default and entered) else "Modified"
        rows.append(
            {
                "clause_number": mf.clause_number,
                "clause_title": mf.field_label,
                "default_value": mf.default_value or "",
                "entered_value": afv.entered_value or "",
                "change_type": change_type,
            }
        )
    return rows


async def compare_clauses(db: AsyncSession, agreement_id: str) -> AIResult:
    key = _cache_key(agreement_id, "comparison")
    cached = await _get_cache(key)
    if cached is not None:
        return AIResult(data=cached, cached=True)

    rows = await _get_deviation_rows(db, agreement_id)
    modified_rows = [row for row in rows if row.get("change_type") in ("Modified", "Filled")]
    prompt = (
        "You are a legal contract analyst for a UAE construction company. "
        "Review these clause modifications to a subcontract agreement. "
        "For each modified clause, identify: what changed, potential legal implication. "
        "Return JSON array: [{clause_number, clause_title, change_summary, implication}].\n\n"
        f"Data:\n{json.dumps(modified_rows, ensure_ascii=False)}"
    )
    data = await _chat_json("Return valid JSON only.", prompt)
    await _set_cache(key, data)
    await _store_ai_review(db, agreement_id, ReviewTypeEnum.comparison, data)
    return AIResult(data=data, cached=False)


async def detect_risks(db: AsyncSession, agreement_id: str) -> AIResult:
    key = _cache_key(agreement_id, "risk")
    cached = await _get_cache(key)
    if cached is not None:
        return AIResult(data=cached, cached=True)

    comparison = await compare_clauses(db, agreement_id)
    prompt = (
        "Rate the legal and financial risk of each modification: 1=none, 2=low, 3=medium, 4=high, 5=critical. "
        "Explain in plain English. Return JSON array: [{clause_number, risk_score, risk_explanation}].\n\n"
        f"Data:\n{json.dumps(comparison.data, ensure_ascii=False)}"
    )
    data = await _chat_json("Return valid JSON only.", prompt)
    await _set_cache(key, data)
    await _store_ai_review(db, agreement_id, ReviewTypeEnum.risk, data)
    return AIResult(data=data, cached=False)


async def generate_summary(db: AsyncSession, agreement_id: str, role: str) -> AIResult:
    key = _cache_key(agreement_id, "summary", role)
    cached = await _get_cache(key)
    if cached is not None:
        return AIResult(data=cached, cached=True)

    deviation_rows = await _get_deviation_rows(db, agreement_id)
    role_instructions = {
        "accounts": "Focus on payment terms, advance, retention, securities, LD rates.",
        "operation_manager": "Focus on scope, programme, milestones, and defects liability period.",
        "gm": "Provide a 5-line executive brief and top 3 risk items.",
    }
    prompt = (
        f"Generate a role-specific summary for role '{role}'. {role_instructions.get(role, '')} "
        "Return JSON object with concise points.\n\n"
        f"Deviation data:\n{json.dumps(deviation_rows, ensure_ascii=False)}"
    )
    data = await _chat_json("Return valid JSON only.", prompt)
    await _set_cache(key, data)
    await _store_ai_review(db, agreement_id, ReviewTypeEnum.summary, data)
    return AIResult(data=data, cached=False)


async def suggest_responses(db: AsyncSession, agreement_id: str) -> AIResult:
    """Draft AI responses for every subcontractor comment on an agreement.

    The spec refers to a "resolution sheet" but the data model stores each
    comment as its own CommentsResolutionSheet row, so the natural key here
    is the agreement's id -- we fetch all rows for it.
    """
    key = _cache_key(agreement_id, "response_suggestion")
    cached = await _get_cache(key)
    if cached is not None:
        return AIResult(data=cached, cached=True)

    rows_res = await db.execute(
        select(CommentsResolutionSheet).where(
            CommentsResolutionSheet.agreement_id == agreement_id
        )
    )
    rows = rows_res.scalars().all()
    if not rows:
        raise ValueError("No resolution sheet rows found for this agreement")

    payload = [
        {
            "comment_id": str(row.id),
            "subcontractor_comment": row.subcontractor_comment,
            "clause_reference": row.clause_reference,
        }
        for row in rows
    ]
    prompt = (
        "Draft a professional contractual response to each subcontractor comment based on the agreement terms. "
        "Be firm but professional. Return JSON array: [{comment_id, suggested_response}].\n\n"
        f"Comments:\n{json.dumps(payload, ensure_ascii=False)}"
    )
    data = await _chat_json("Return valid JSON only.", prompt)
    await _set_cache(key, data)
    await _store_ai_review(db, agreement_id, ReviewTypeEnum.response_suggestion, data)
    return AIResult(data=data, cached=False)


async def validate_revision(db: AsyncSession, agreement_id: str) -> AIResult:
    """Check whether the Admin's revisions address every subcontractor comment."""
    key = _cache_key(agreement_id, "validation")
    cached = await _get_cache(key)
    if cached is not None:
        return AIResult(data=cached, cached=True)

    rows_res = await db.execute(
        select(CommentsResolutionSheet).where(
            CommentsResolutionSheet.agreement_id == agreement_id
        )
    )
    rows = rows_res.scalars().all()
    if not rows:
        raise ValueError("No resolution sheet rows found for this agreement")

    data_payload = [
        {
            "comment_id": str(row.id),
            "subcontractor_comment": row.subcontractor_comment,
            "final_response": row.final_response,
            "pd_response": row.pd_response,
            "om_response": row.om_response,
        }
        for row in rows
    ]
    prompt = (
        "After admin revisions, validate whether each comment appears addressed. "
        "Return JSON array: [{comment_id, is_addressed, explanation}].\n\n"
        f"Data:\n{json.dumps(data_payload, ensure_ascii=False)}"
    )
    data = await _chat_json("Return valid JSON only.", prompt)
    await _set_cache(key, data)
    await _store_ai_review(db, agreement_id, ReviewTypeEnum.validation, data)
    return AIResult(data=data, cached=False)
