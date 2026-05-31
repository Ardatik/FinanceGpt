from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import re

from fastapi import FastAPI
import httpx
from pydantic import BaseModel, Field


app = FastAPI(title="FinancePay Demo Payment Service")


class PaymentConfirmIn(BaseModel):
    payment_id: str
    merchant: str = Field(default='ООО "Яндекс Маркет"')
    amount: Decimal
    bank: str


class SbpPaymentRequestIn(BaseModel):
    payment_id: str
    bank: str
    qr_payload: str
    callback_url: str
    amount_hint: Decimal | None = None


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "payment-demo"}


def qr_amount_hint(payload: str) -> Decimal | None:
    for pattern in (
        r"(?:amount|total|summ?)=([0-9]+(?:[.,][0-9]{1,2})?)",
        r"(?:sum|am)=([0-9]+)",
    ):
        match = re.search(pattern, payload, flags=re.IGNORECASE)
        if not match:
            continue
        raw = match.group(1).replace(",", ".")
        try:
            value = Decimal(raw)
        except Exception:
            continue
        if pattern.startswith("(?:sum") and value > 100:
            value = value / Decimal("100")
        if value > 0:
            return value
    return None


def build_mock_items(total: Decimal | None) -> list[dict]:
    if total and total > 0:
        coffee = (total * Decimal("0.32")).quantize(Decimal("1"))
        food = (total * Decimal("0.38")).quantize(Decimal("1"))
        household = total - coffee - food
        return [
            {
                "title": "Кофе молотый",
                "description": "Пачка кофе для домашнего приготовления",
                "quantity": "1",
                "unit_price": str(coffee),
                "amount": str(coffee),
            },
            {
                "title": "Продукты для ужина",
                "description": "Базовая продуктовая корзина",
                "quantity": "1",
                "unit_price": str(food),
                "amount": str(food),
            },
            {
                "title": "Товары для дома",
                "description": "Хозяйственная покупка",
                "quantity": "1",
                "unit_price": str(household),
                "amount": str(household),
            },
        ]
    return [
        {
            "title": "Кофе молотый",
            "description": "Пачка кофе для домашнего приготовления",
            "quantity": "1",
            "unit_price": "420",
            "amount": "420",
        },
        {
            "title": "Паста цельнозерновая",
            "description": "Базовый продукт для домашней еды",
            "quantity": "2",
            "unit_price": "185",
            "amount": "370",
        },
        {
            "title": "Бытовая химия",
            "description": "Плановая хозяйственная покупка",
            "quantity": "1",
            "unit_price": "500",
            "amount": "500",
        },
    ]


@app.post("/payments/sbp-request")
async def request_sbp_payment(payload: SbpPaymentRequestIn) -> dict:
    total_hint = payload.amount_hint or qr_amount_hint(payload.qr_payload)
    items = build_mock_items(total_hint)
    total = sum(Decimal(item["amount"]) for item in items)
    callback_payload = {
        "payment_id": payload.payment_id,
        "merchant": 'ООО "Яндекс Маркет"',
        "items": items,
        "total_amount": str(total),
        "status": "confirmed",
        "paid_at": datetime.now(timezone.utc).isoformat(),
    }
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.post(payload.callback_url, json=callback_payload)
        response.raise_for_status()
    return {
        "payment_id": payload.payment_id,
        "status": "sent_to_backend",
        "merchant": callback_payload["merchant"],
        "total_amount": str(total),
        "items_count": len(items),
    }


@app.post("/payments/confirm")
async def confirm_payment(payload: PaymentConfirmIn) -> dict:
    return {
        "payment_id": payload.payment_id,
        "merchant": payload.merchant,
        "amount": str(payload.amount),
        "bank": payload.bank,
        "status": "confirmed",
        "paid_at": datetime.now(timezone.utc).isoformat(),
        "receipt_sender": 'ООО "Яндекс Маркет"',
        "receipt_status": "queued",
        "message": "Демо-оплата подтверждена продавцом.",
    }
