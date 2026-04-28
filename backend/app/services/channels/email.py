from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import settings


def send_email(*, to_email: str, subject: str, body: str) -> dict:
    cleaned_to = to_email.strip()
    if not cleaned_to:
        raise ValueError("Recipient email is required")

    if settings.channel_stub_mode or not settings.smtp_host:
        return {
            "status": "stub_sent",
            "provider": "stub",
            "to_email": cleaned_to,
            "subject": subject,
        }

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = cleaned_to
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)
    return {
        "status": "sent",
        "provider": "smtp",
        "to_email": cleaned_to,
        "subject": subject,
    }
