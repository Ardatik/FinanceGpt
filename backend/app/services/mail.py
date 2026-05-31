from __future__ import annotations

import asyncio
import email
import imaplib
import re
from datetime import datetime, timezone
from decimal import Decimal
from email import policy
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime
from typing import Any

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.models import MailIntegration, Transaction
from app.services.ai import AIService
from app.services.serializers import json_safe


ALLOWED_SENDERS = ['ООО "Яндекс Маркет"', "Yandex Market", "Яндекс Маркет"]
MAX_FETCH_MESSAGES = 25


def build_mail_oauth_url(state: str) -> str | None:
    settings = get_settings()
    if not settings.is_mailru_oauth_enabled:
        return None
    return (
        f"{settings.mailru_auth_url}?client_id={settings.mailru_client_id}"
        f"&response_type=code&scope={settings.mailru_scope}"
        f"&redirect_uri={settings.mailru_redirect_uri}&state={state}"
    )


def parse_yandex_market_receipt(raw_message: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(raw_message, "lxml")
    text = soup.get_text("\n") if soup else raw_message
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    items: list[dict[str, Any]] = []
    pattern = re.compile(r"(?P<title>.+?)\s+[xх]\s*(?P<qty>\d+(?:[.,]\d+)?)\s+—?\s*(?P<price>\d+(?:[.,]\d+)?)")
    for line in lines:
        match = pattern.search(line)
        if not match:
            continue
        qty = Decimal(match.group("qty").replace(",", "."))
        price = Decimal(match.group("price").replace(",", "."))
        items.append(
            {
                "title": match.group("title").strip(),
                "quantity": qty,
                "unit_price": price,
                "amount": qty * price,
            }
        )
    return items


def decode_mime(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def message_to_text(message: Message) -> str:
    parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type not in {"text/plain", "text/html"}:
                continue
            try:
                parts.append(part.get_content())
            except Exception:
                payload = part.get_payload(decode=True)
                if payload:
                    parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="ignore"))
    else:
        try:
            parts.append(message.get_content())
        except Exception:
            payload = message.get_payload(decode=True)
            if payload:
                parts.append(payload.decode(message.get_content_charset() or "utf-8", errors="ignore"))
    return "\n".join(parts)


def is_allowed_market_message(message: Message, text: str) -> bool:
    from_header = decode_mime(message.get("From"))
    subject = decode_mime(message.get("Subject"))
    haystack = f"{from_header}\n{subject}\n{text}".lower()
    return any(sender.lower() in haystack for sender in ALLOWED_SENDERS)


def parse_message_date(message: Message) -> datetime:
    date_header = message.get("Date")
    if not date_header:
        return datetime.now(timezone.utc)
    parsed = parsedate_to_datetime(date_header)
    if not parsed:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def receipt_total_fallback(raw_text: str) -> Decimal | None:
    patterns = [
        r"(?:итого|сумма|оплачено|к\s+оплате)[^\d]{0,20}(\d+(?:[.,]\d{1,2})?)",
        r"(\d+(?:[.,]\d{1,2})?)\s*(?:₽|руб)",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, raw_text, flags=re.IGNORECASE)
        if matches:
            value = matches[-1].replace(",", ".")
            try:
                return Decimal(value)
            except Exception:
                continue
    return None


def fetch_recent_market_messages(mailbox_email: str, app_password: str) -> list[dict[str, Any]]:
    settings = get_settings()
    imap_cls = imaplib.IMAP4_SSL if settings.mail_imap_ssl else imaplib.IMAP4
    imap = imap_cls(settings.mail_imap_host, settings.mail_imap_port)
    try:
        imap.login(mailbox_email, app_password)
        imap.select("INBOX")
        status, data = imap.search(None, "ALL")
        if status != "OK" or not data or not data[0]:
            return []
        message_ids = data[0].split()[-MAX_FETCH_MESSAGES:]
        result: list[dict[str, Any]] = []
        for message_id in reversed(message_ids):
            status, payload = imap.fetch(message_id, "(RFC822)")
            if status != "OK" or not payload:
                continue
            raw_bytes = next((item[1] for item in payload if isinstance(item, tuple)), None)
            if not raw_bytes:
                continue
            message = email.message_from_bytes(raw_bytes, policy=policy.default)
            text = message_to_text(message)
            if not is_allowed_market_message(message, text):
                continue
            result.append(
                {
                    "text": text,
                    "from": decode_mime(message.get("From")),
                    "subject": decode_mime(message.get("Subject")),
                    "date": parse_message_date(message),
                }
            )
        return result
    finally:
        try:
            imap.logout()
        except Exception:
            pass


async def test_mailru_imap_credentials(mailbox_email: str, app_password: str) -> None:
    await asyncio.to_thread(fetch_recent_market_messages, mailbox_email, app_password)


async def get_active_mail_integration(session: AsyncSession, user_id: Any) -> MailIntegration | None:
    result = await session.execute(
        select(MailIntegration)
        .where(
            MailIntegration.user_id == user_id,
            MailIntegration.provider == "mailru_imap",
            MailIntegration.is_active.is_(True),
        )
        .order_by(MailIntegration.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_transactions_from_items(
    session: AsyncSession,
    *,
    user_id: Any,
    items: list[dict[str, Any]],
    receipt: dict[str, Any],
) -> int:
    ai = AIService()
    created = 0
    for item in items:
        category = await ai.categorize_purchase(
            title=item["title"],
            merchant='ООО "Яндекс Маркет"',
            amount=item["amount"],
        )
        session.add(
            Transaction(
                user_id=user_id,
                source="mailru_imap",
                merchant='ООО "Яндекс Маркет"',
                title=item["title"],
                amount=item["amount"],
                quantity=item.get("quantity", Decimal("1")),
                unit_price=item.get("unit_price", item["amount"]),
                purchased_at=receipt.get("date") or datetime.now(timezone.utc),
                category=category.category,
                category_kind=category.category_kind,
                impulse_type=category.impulse_type,
                raw_payload=json_safe(
                    {
                        "from": receipt.get("from"),
                        "subject": receipt.get("subject"),
                        "payment_id": receipt.get("payment_id"),
                        "source": "imap",
                    }
                ),
            )
        )
        created += 1
    await session.commit()
    return created


async def sync_mailru_imap(session: AsyncSession, *, user_id: Any, integration: MailIntegration) -> int:
    if not integration.mailbox_email or not integration.access_token:
        return 0
    app_password = decrypt_secret(integration.access_token)
    receipts = await asyncio.to_thread(fetch_recent_market_messages, integration.mailbox_email, app_password)
    created = 0
    for receipt in receipts[:5]:
        items = parse_yandex_market_receipt(receipt["text"])
        if not items:
            total = receipt_total_fallback(receipt["text"])
            if total:
                items = [
                    {
                        "title": "Покупка Яндекс Маркет",
                        "quantity": Decimal("1"),
                        "unit_price": total,
                        "amount": total,
                    }
                ]
        if items:
            created += await create_transactions_from_items(session, user_id=user_id, items=items, receipt=receipt)
    return created


async def create_demo_market_transactions(
    session: AsyncSession,
    *,
    user_id: Any,
    payment_id: Any | None = None,
    amount: Decimal | None = None,
) -> int:
    total = amount or Decimal("1290")
    demo_items = [
        {"title": "Продукты Яндекс Маркет", "quantity": Decimal("1"), "unit_price": total, "amount": total},
    ]
    created = 0
    receipt = {
        "from": 'ООО "Яндекс Маркет"',
        "subject": "Демо-чек",
        "date": datetime.now(timezone.utc),
        "payment_id": str(payment_id) if payment_id else None,
    }
    created += await create_transactions_from_items(session, user_id=user_id, items=demo_items, receipt=receipt)
    return created
