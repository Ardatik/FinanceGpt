from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import quote
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import async_session_maker, get_session
from app.models import Payment, Transaction, User
from app.schemas.payment import PaymentMockCallbackIn, PaymentOut, PaymentQrRequestIn, PaymentStartIn
from app.services.ai import AIService, fallback_category
from app.services.mail import create_demo_market_transactions
from app.services.portrait import update_portrait_from_receipt
from app.services.serializers import json_safe, payment_to_dict


router = APIRouter()
logger = logging.getLogger(__name__)


BANK_LINKS = {
    "sber": ("bank100000000111://qr.nspk.ru/demo", "https://www.sberbank.com/ru/person/paymentsandremittances"),
    "vtb": ("vtbpay://qr.nspk.ru/demo", "https://www.vtb.ru/personal/platezhi-i-perevody/"),
    "alfa": ("alfabank://qr.nspk.ru/demo", "https://alfabank.ru/everyday/payments/"),
    "tbank": ("tbank://qr.nspk.ru/demo", "https://www.tbank.ru/payments/"),
}


def build_bank_redirect(bank: str, qr_payload: str | None, amount: Decimal | None) -> tuple[str, str]:
    deeplink, fallback = BANK_LINKS[bank]
    if qr_payload and qr_payload.startswith(("https://", "http://")):
        fallback = qr_payload

    params = []
    if qr_payload:
        params.append(f"qr={quote(qr_payload, safe='')}")
    if amount and amount > 0:
        params.append(f"amount={amount}")
    return f"{deeplink}?{'&'.join(params)}" if params else deeplink, fallback


async def delayed_receipt_job(user_id: str, payment_id: str, amount: str) -> None:
    async with async_session_maker() as session:
        await create_demo_market_transactions(
            session,
            user_id=UUID(user_id),
            payment_id=payment_id,
            amount=Decimal(amount),
        )


async def enrich_sbp_receipt_job(payment_id: str) -> None:
    try:
        async with async_session_maker() as session:
            payment = await session.get(Payment, UUID(payment_id))
            if not payment or payment.status != "confirmed":
                return

            payload = payment.external_payload or {}
            items = payload.get("items") or []
            if not items:
                return

            ai = AIService()
            result = await session.execute(
                select(Transaction).where(
                    Transaction.user_id == payment.user_id,
                    Transaction.source == "sbp_mock",
                    Transaction.raw_payload.contains({"payment_id": str(payment.id)}),
                )
            )
            transactions = result.scalars().all()
            for transaction in transactions:
                category = await ai.categorize_purchase(
                    title=transaction.title,
                    merchant=transaction.merchant,
                    amount=transaction.amount,
                )
                transaction.category = category.category
                transaction.category_kind = category.category_kind
                transaction.impulse_type = category.impulse_type
                transaction.optimized = category.category_kind == "optimizable"

            await update_portrait_from_receipt(
                session,
                user_id=payment.user_id,
                payment_id=payment.id,
                merchant=payment.merchant,
                items=items,
            )
            payment.external_payload = json_safe(
                {
                    **payload,
                    "ai_enrichment": {
                        "status": "completed",
                        "updated_at": datetime.now(timezone.utc),
                    },
                }
            )
            await session.commit()
    except Exception:
        logger.exception("SBP receipt enrichment failed for payment %s", payment_id)


def schedule_sbp_enrichment(request: Request, payment_id: UUID) -> None:
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler:
        scheduler.add_job(
            enrich_sbp_receipt_job,
            "date",
            run_date=datetime.now(timezone.utc),
            args=[str(payment_id)],
            id=f"sbp-enrich-{payment_id}",
            replace_existing=True,
        )
        return
    asyncio.create_task(enrich_sbp_receipt_job(str(payment_id)))


@router.post("/start", response_model=PaymentOut)
async def start_payment(
    payload: PaymentStartIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    deeplink, fallback = build_bank_redirect(payload.bank, payload.qr_payload, payload.amount)
    qr_payload = payload.qr_payload.strip() if payload.qr_payload else None
    deeplink_url = deeplink
    payment = Payment(
        user_id=current_user.id,
        bank=payload.bank,
        amount=payload.amount,
        merchant=payload.merchant,
        status="created",
        deeplink=deeplink_url,
        fallback_url=fallback,
        external_payload={
            "mvp": True,
            "note": "Оплата СБП доступна на телефоне.",
            "qr_payload": qr_payload,
            "scanned_qr": bool(qr_payload),
        },
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment_to_dict(payment)


@router.post("/sbp/request", response_model=PaymentOut)
async def request_sbp_payment(
    payload: PaymentQrRequestIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    settings = get_settings()
    amount = payload.amount_hint or Decimal("0")
    deeplink, fallback = build_bank_redirect(payload.bank, payload.qr_payload, amount)
    payment = Payment(
        user_id=current_user.id,
        bank=payload.bank,
        amount=amount,
        merchant="Ожидаем данные продавца",
        status="pending",
        deeplink=deeplink,
        fallback_url=fallback,
        external_payload={
            "flow": "sbp_qr_mock",
            "qr_payload": payload.qr_payload,
            "note": "Ожидаем mock-чек от payment_service.",
        },
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)

    request_payload = {
        "payment_id": str(payment.id),
        "bank": payload.bank,
        "qr_payload": payload.qr_payload,
        "amount_hint": str(payload.amount_hint) if payload.amount_hint is not None else None,
        "callback_url": settings.payment_callback_url,
    }
    try:
        timeout = httpx.Timeout(25.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{settings.payment_service_url}/payments/sbp-request", json=request_payload)
            response.raise_for_status()
    except Exception as exc:
        payment.status = "failed"
        payment.external_payload = {
            **(payment.external_payload or {}),
            "payment_service_error": str(exc),
        }
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="payment_service не смог обработать запрос на оплату",
        ) from exc

    await session.refresh(payment)
    return payment_to_dict(payment)


@router.post("/sbp/callback", response_model=PaymentOut)
async def sbp_payment_callback(
    payload: PaymentMockCallbackIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    payment = await session.get(Payment, payload.payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Платеж не найден")
    if payment.status == "confirmed":
        if (payment.external_payload or {}).get("ai_enrichment", {}).get("status") != "completed":
            schedule_sbp_enrichment(request, payment.id)
        return payment_to_dict(payment)
    if payload.status != "confirmed":
        payment.status = payload.status
        payment.external_payload = json_safe(payload.model_dump())
        await session.commit()
        await session.refresh(payment)
        return payment_to_dict(payment)

    merchant = payload.merchant.strip()
    paid_at = payload.paid_at or datetime.now(timezone.utc)
    original_payload = payment.external_payload or {}

    payment.status = "confirmed"
    payment.confirmed_at = paid_at
    payment.amount = payload.total_amount
    payment.merchant = merchant
    payment.external_payload = json_safe(
        {
            **payload.model_dump(),
            "confirmation": "backend_received_and_persisted_mock_receipt",
            "qr_payload": original_payload.get("qr_payload"),
            "ai_enrichment": {"status": "queued"},
        }
    )

    for item in payload.items:
        category = fallback_category(item.title, merchant)
        session.add(
            Transaction(
                user_id=payment.user_id,
                source="sbp_mock",
                merchant=merchant,
                title=item.title,
                amount=item.amount,
                quantity=item.quantity,
                unit_price=item.unit_price,
                purchased_at=paid_at,
                category=category.category,
                category_kind=category.category_kind,
                impulse_type=category.impulse_type,
                optimized=category.category_kind == "optimizable",
                raw_payload=json_safe(
                    {
                        "payment_id": str(payment.id),
                        "source": "payment_service",
                        "qr_payload": original_payload.get("qr_payload"),
                        "item": item.model_dump(),
                    }
                ),
            )
        )

    await session.commit()
    await session.refresh(payment)
    schedule_sbp_enrichment(request, payment.id)
    return payment_to_dict(payment)


@router.post("/{payment_id}/confirm", response_model=PaymentOut)
async def confirm_payment(
    payment_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    settings = get_settings()
    payment = await session.get(Payment, payment_id)
    if not payment or payment.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Платеж не найден")
    payload = {
        "payment_id": str(payment.id),
        "merchant": payment.merchant,
        "amount": str(payment.amount),
        "bank": payment.bank,
    }
    external_payload = {"status": "confirmed", **payload}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post(f"{settings.payment_service_url}/payments/confirm", json=payload)
            response.raise_for_status()
            external_payload = response.json()
    except Exception:
        external_payload["demo_fallback"] = True
    payment.status = "confirmed"
    payment.confirmed_at = datetime.now(timezone.utc)
    payment.external_payload = external_payload
    await session.commit()
    await session.refresh(payment)

    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler:
        scheduler.add_job(
            delayed_receipt_job,
            "date",
            run_date=datetime.now(timezone.utc) + timedelta(seconds=settings.receipt_parse_delay_seconds),
            args=[str(current_user.id), str(payment.id), str(payment.amount)],
            id=f"receipt-{payment.id}",
            replace_existing=True,
        )
    else:
        await create_demo_market_transactions(session, user_id=current_user.id, payment_id=payment.id, amount=payment.amount)
    return payment_to_dict(payment)
