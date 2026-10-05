"""Push parity with email. Hooked into send_email (email_service.py), the one
choke point every email-sending path already goes through."""
import asyncio
import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import database
from config import get_settings
from models.agreement import Agreement
from models.device import DeviceToken, Notification
from models.user import User

logger = logging.getLogger(__name__)
_fcm_ready: bool | None = None


def _fcm_send(tokens: list[str], title: str, body: str, agreement_id: str | None) -> list[str]:
    """Blocking; returns tokens FCM says are dead. No-op when creds not configured."""
    global _fcm_ready
    path = get_settings().FIREBASE_CREDENTIALS_PATH
    if not path:
        return []
    import firebase_admin
    from firebase_admin import credentials, messaging

    if _fcm_ready is None:
        firebase_admin.initialize_app(credentials.Certificate(path))
        _fcm_ready = True
    msgs = [
        messaging.Message(
            token=t,
            notification=messaging.Notification(title=title, body=body[:300]),
            data={"agreement_id": agreement_id or ""},
        )
        for t in tokens
    ]
    resp = messaging.send_each(msgs)
    return [t for t, r in zip(tokens, resp.responses) if not r.success and isinstance(r.exception, (messaging.UnregisteredError, messaging.SenderIdMismatchError))]


async def record_and_push(db: AsyncSession, to_email: str, subject: str, body: str) -> None:
    user = (await db.execute(select(User).where(User.email == to_email, User.is_active.is_(True)))).scalar_one_or_none()
    if not user:
        return  # e.g. subcontractor emails — external, never a user
    # ponytail: match agreement by reference in the text; add an agreement_id kwarg to send_email if table gets huge
    text = f"{subject}\n{body}"
    refs = (await db.execute(select(Agreement.id, Agreement.reference_number))).all()
    agreement_id = next((a for a, ref in refs if ref and ref in text), None)
    db.add(Notification(user_id=user.id, agreement_id=agreement_id, title=subject, body=body))
    await db.commit()

    tokens = (await db.execute(select(DeviceToken.token).where(DeviceToken.user_id == user.id))).scalars().all()
    if tokens:
        dead = await asyncio.to_thread(_fcm_send, list(tokens), subject, body, str(agreement_id) if agreement_id else None)
        if dead:
            await db.execute(delete(DeviceToken).where(DeviceToken.token.in_(dead)))
            await db.commit()


async def notify_by_email(to_email: str, subject: str, body: str) -> None:
    try:
        async with database.AsyncSessionLocal() as db:
            await record_and_push(db, to_email, subject, body)
    except Exception as exc:  # noqa: BLE001 — best-effort like email
        logger.warning("Push/notification failed for %s: %s", to_email, exc)
