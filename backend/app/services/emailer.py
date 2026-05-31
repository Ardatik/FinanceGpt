from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings


async def send_magic_code(email: str, code: str, *, purpose: str = "login") -> None:
    settings = get_settings()
    if not settings.is_smtp_enabled:
        return

    subject = "Код входа FinancePay"
    if purpose == "cushion_recovery":
        subject = "Восстановление кодового слова FinancePay"

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = email
    message["Subject"] = subject
    message.set_content(
        "Ваш одноразовый код: {code}\n\n"
        "Если вы не запрашивали код, просто проигнорируйте это письмо.".format(code=code)
    )

    def _send() -> None:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)

    await asyncio.to_thread(_send)
