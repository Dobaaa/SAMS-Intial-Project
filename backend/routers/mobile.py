import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from middleware.rbac import get_current_user
from models.device import DeviceToken, Notification
from models.user import User

router = APIRouter(tags=["mobile"])


class DevicePayload(BaseModel):
    token: str
    platform: str = "unknown"


@router.post("/devices", status_code=204)
async def register_device(p: DevicePayload, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_current_user)) -> None:
    """Upsert: a token moving to another account (shared phone) is reassigned."""
    row = (await db.execute(select(DeviceToken).where(DeviceToken.token == p.token))).scalar_one_or_none()
    if row:
        row.user_id, row.platform = user.id, p.platform
    else:
        db.add(DeviceToken(user_id=user.id, token=p.token, platform=p.platform))
    await db.commit()


@router.delete("/devices", status_code=204)
async def unregister_device(token: str = Query(...), db: AsyncSession = Depends(get_db_session), user: User = Depends(get_current_user)) -> None:
    await db.execute(delete(DeviceToken).where(DeviceToken.token == token, DeviceToken.user_id == user.id))
    await db.commit()


def _row(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "agreement_id": str(n.agreement_id) if n.agreement_id else None,
        "title": n.title,
        "body": n.body,
        "read": n.read_at is not None,
        "created_at": n.created_at.isoformat(),
    }


@router.get("/notifications")
async def list_notifications(
    after: datetime | None = None,
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> dict:
    """`after` (created_at of newest seen) lets the app poll for new ones cheaply."""
    q = select(Notification).where(Notification.user_id == user.id)
    if after:
        q = q.where(Notification.created_at > after)
    rows = (await db.execute(q.order_by(desc(Notification.created_at)).limit(limit))).scalars().all()
    unread = (await db.execute(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)))).scalar_one()
    return {"unread": unread, "items": [_row(n) for n in rows]}


@router.post("/notifications/{notification_id}/read", status_code=204)
async def mark_read(notification_id: uuid.UUID, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_current_user)) -> None:
    res = await db.execute(
        update(Notification).where(Notification.id == notification_id, Notification.user_id == user.id).values(read_at=datetime.now(UTC))
    )
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.commit()
