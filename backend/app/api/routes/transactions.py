from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import Transaction, User
from app.schemas.transaction import ManualTransactionIn, TransactionOut
from app.services.ai import AIService
from app.services.serializers import json_safe, transaction_to_dict


router = APIRouter()


@router.get("", response_model=list[TransactionOut])
async def list_transactions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    result = await session.execute(
        select(Transaction).where(Transaction.user_id == current_user.id).order_by(Transaction.purchased_at.desc())
    )
    return [transaction_to_dict(transaction) for transaction in result.scalars().all()]


@router.post("", response_model=TransactionOut)
async def create_manual_transaction(
    payload: ManualTransactionIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ai = AIService()
    category = await ai.categorize_purchase(
        title=payload.title,
        merchant=payload.merchant,
        amount=payload.amount,
    )
    transaction = Transaction(
        user_id=current_user.id,
        source="manual",
        merchant=payload.merchant,
        title=payload.title,
        amount=payload.amount,
        quantity=1,
        unit_price=payload.amount,
        purchased_at=payload.purchased_at or datetime.now(timezone.utc),
        category=payload.category or category.category,
        category_kind=payload.category_kind or category.category_kind,
        impulse_type=category.impulse_type,
        raw_payload=json_safe(payload.model_dump()),
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return transaction_to_dict(transaction)
