"""Transactional email. Uses SMTP when configured; in development, writes messages to a local
outbox folder instead (never to logs, so reset links don't leak into log aggregation)."""

import asyncio
import logging
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage

from app.core.config import get_settings

log = logging.getLogger(__name__)


def _send_smtp(msg: EmailMessage) -> None:
    s = get_settings()
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        if s.smtp_username:
            smtp.login(s.smtp_username, s.smtp_password)
        smtp.send_message(msg)


def _write_outbox(msg: EmailMessage) -> None:
    outbox = get_settings().local_storage_dir / "dev-outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + ".eml"
    (outbox / name).write_bytes(bytes(msg))
    log.info("Development email written to storage/dev-outbox/%s", name)


async def send_email(to: str, subject: str, text: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = s.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    try:
        if s.smtp_host:
            await asyncio.to_thread(_send_smtp, msg)
        else:
            await asyncio.to_thread(_write_outbox, msg)
    except (OSError, smtplib.SMTPException) as exc:
        # Don't surface delivery failures to the requester (it would leak whether the account exists).
        log.error("Email delivery failed: %s", type(exc).__name__)
