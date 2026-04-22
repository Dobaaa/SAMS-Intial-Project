from email.message import EmailMessage

import aiosmtplib

from config import get_settings

settings = get_settings()


async def send_email(to_email: str, subject: str, body: str) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASS:
        return

    message = EmailMessage()
    message["From"] = settings.SMTP_USER
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=587,
        start_tls=True,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASS,
    )
