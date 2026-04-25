import logging
from email.message import EmailMessage

import aiosmtplib

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def send_email(to_email: str, subject: str, body: str) -> None:
    """Send a notification email; never raises on transport failure.

    Email is non-load-bearing — workflow transitions (approve, return,
    send-to-subcontractor) must succeed even when SMTP is unreachable
    (local dev, network outage, misconfigured creds). Failures are logged
    and swallowed so the calling business logic keeps moving.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASS:
        # SMTP intentionally not configured (e.g. local dev) — silent no-op.
        return

    message = EmailMessage()
    message["From"] = settings.SMTP_USER
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=587,
            start_tls=True,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASS,
        )
    except Exception as exc:  # noqa: BLE001 — email is best-effort, log everything
        logger.warning(
            "Failed to send email to %s (subject=%r): %s. Workflow continues.",
            to_email,
            subject,
            exc,
        )
