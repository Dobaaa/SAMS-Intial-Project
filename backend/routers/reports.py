import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db_session
from middleware.rbac import require_role
from models.agreement import Agreement, AgreementStatusEnum
from models.audit import AuditLog
from models.master import MasterTemplate
from models.user import RoleEnum, User

MAX_AUDIT_PAGE_SIZE = 200

router = APIRouter(prefix="/reports", tags=["reports"])


def _status_label(value: str) -> str:
    labels = {
        "under_drafting": "Under Drafting",
        "under_internal_review": "Under Internal Review",
        "draft_forwarded_to_subcontractor": "Draft Forwarded to Subcontractor",
        "under_subcontractor_review": "Under Subcontractor Review",
        "under_subcontractor_signature": "Under Subcontractor Signature",
        "under_bgcc_revision": "Under BGCC Revision",
        "under_gm_signature": "Under GM Signature",
        "completed": "Completed",
    }
    return labels.get(value, value)


@router.get("/dashboard/summary", dependencies=[Depends(require_role(RoleEnum.admin))])
async def dashboard_summary(db: AsyncSession = Depends(get_db_session)) -> dict:
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total = (await db.execute(select(func.count(Agreement.id)))).scalar_one() or 0
    # "Under Review" == any status where BGCC is actively working on the
    # agreement (internal review chain, revision after comments, or awaiting
    # GM's countersignature). Excludes drafting (not yet submitted) and all
    # subcontractor-facing statuses.
    under_review = (
        await db.execute(
            select(func.count(Agreement.id)).where(
                Agreement.current_status.in_(
                    [
                        AgreementStatusEnum.under_internal_review,
                        AgreementStatusEnum.under_bgcc_revision,
                        AgreementStatusEnum.under_gm_signature,
                    ]
                )
            )
        )
    ).scalar_one() or 0
    with_subcontractor = (
        await db.execute(
            select(func.count(Agreement.id)).where(
                Agreement.current_status.in_(
                    [
                        AgreementStatusEnum.draft_forwarded_to_subcontractor,
                        AgreementStatusEnum.under_subcontractor_review,
                        AgreementStatusEnum.under_subcontractor_signature,
                    ]
                )
            )
        )
    ).scalar_one() or 0
    completed_this_month = (
        await db.execute(
            select(func.count(Agreement.id)).where(
                and_(
                    Agreement.current_status == AgreementStatusEnum.completed,
                    Agreement.status_updated_on >= month_start,
                )
            )
        )
    ).scalar_one() or 0

    return {
        "total_agreements": total,
        "under_review": under_review,
        "with_subcontractor": with_subcontractor,
        "completed_this_month": completed_this_month,
    }


@router.get("/dashboard/agreements", dependencies=[Depends(require_role(RoleEnum.admin))])
async def dashboard_agreements(
    status_filter: str | None = Query(default=None, alias="status"),
    project_id: uuid.UUID | None = None,
    subcontractor_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    reference_number: str | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    query = (
        select(Agreement)
        .options(selectinload(Agreement.project), selectinload(Agreement.subcontractor))
        .order_by(desc(Agreement.created_at))
    )
    if status_filter:
        query = query.where(Agreement.current_status == AgreementStatusEnum(status_filter))
    if project_id:
        query = query.where(Agreement.project_id == project_id)
    if subcontractor_id:
        query = query.where(Agreement.subcontractor_id == subcontractor_id)
    if date_from:
        query = query.where(Agreement.created_at >= date_from)
    if date_to:
        query = query.where(Agreement.created_at <= date_to + timedelta(days=1))
    if reference_number:
        query = query.where(Agreement.reference_number.ilike(f"%{reference_number}%"))

    result = await db.execute(query)
    items = result.scalars().all()

    # Per-agreement counts of unresolved Workflow Review comments (PD / Accounts /
    # OM / GM main-chain steps only). Resolution-chain comments are excluded so
    # the badge reflects what is visible on the Workflow Review page.
    from models.workflow import CommentStatusEnum, WorkflowComment, WorkflowStep
    from services.workflow_engine import RESOLUTION_STEP_NAMES

    comment_counts: dict[uuid.UUID, int] = {}
    if items:
        agr_ids = [a.id for a in items]
        cc_res = await db.execute(
            select(WorkflowComment.agreement_id, func.count(WorkflowComment.id))
            .join(WorkflowStep, WorkflowComment.workflow_step_id == WorkflowStep.id)
            .where(
                WorkflowComment.agreement_id.in_(agr_ids),
                WorkflowComment.status != CommentStatusEnum.resolved,
                ~WorkflowStep.step_name.in_(RESOLUTION_STEP_NAMES),
            )
            .group_by(WorkflowComment.agreement_id)
        )
        comment_counts = {row[0]: row[1] for row in cc_res.all()}

    return [
        {
            "id": str(a.id),
            "reference_number": a.reference_number,
            "project_name": a.project.project_name if a.project else None,
            "subcontractor_name": a.subcontractor.company_name if a.subcontractor else None,
            "status": a.current_status.value,
            "status_label": _status_label(a.current_status.value),
            "status_updated_on": a.status_updated_on.isoformat() if a.status_updated_on else None,
            "gm_approval_date": a.gm_approval_date.isoformat() if a.gm_approval_date else None,
            "open_returned_comments": int(comment_counts.get(a.id, 0)),
        }
        for a in items
    ]


@router.get("/audit-log", dependencies=[Depends(require_role(RoleEnum.admin))])
async def audit_log(
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_AUDIT_PAGE_SIZE),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    query = select(AuditLog).options(selectinload(AuditLog.user)).order_by(desc(AuditLog.created_at))
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action == action)
    if date_from:
        query = query.where(AuditLog.created_at >= date_from)
    if date_to:
        query = query.where(AuditLog.created_at <= date_to + timedelta(days=1))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    paged = query.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(paged)).scalars().all()
    return {
        "items": [
            {
                "id": str(row.id),
                "user_name": row.user.name if row.user else None,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": str(row.entity_id) if row.entity_id else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/masters/active-versions", dependencies=[Depends(require_role(RoleEnum.admin))])
async def active_master_versions(db: AsyncSession = Depends(get_db_session)) -> list[dict]:
    result = await db.execute(
        select(MasterTemplate).where(MasterTemplate.is_active.is_(True)).order_by(MasterTemplate.type.asc())
    )
    rows = result.scalars().all()
    return [
        {
            "id": str(row.id),
            "type": row.type.value,
            "version_number": row.version_number,
            "version_date": row.version_date.isoformat(),
        }
        for row in rows
    ]
