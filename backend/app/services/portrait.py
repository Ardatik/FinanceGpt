from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile, UserFinancialPortrait
from app.services.ai import AIService
from app.services.serializers import json_safe, profile_to_dict


async def get_user_portrait(session: AsyncSession, user_id: Any) -> UserFinancialPortrait | None:
    result = await session.execute(select(UserFinancialPortrait).where(UserFinancialPortrait.user_id == user_id))
    return result.scalar_one_or_none()


async def update_portrait_from_receipt(
    session: AsyncSession,
    *,
    user_id: Any,
    payment_id: Any,
    merchant: str,
    items: list[dict[str, Any]],
) -> UserFinancialPortrait:
    profile_result = await session.execute(select(Profile).where(Profile.user_id == user_id))
    profile = profile_result.scalar_one_or_none()
    portrait = await get_user_portrait(session, user_id)
    if not portrait:
        portrait = UserFinancialPortrait(user_id=user_id, data={})
        session.add(portrait)

    receipt = {
        "payment_id": str(payment_id),
        "merchant": merchant,
        "items": items,
        "received_at": datetime.now(timezone.utc),
    }
    result = await AIService().update_financial_portrait(
        existing_portrait=portrait.data or {},
        profile=profile_to_dict(profile) if profile else None,
        receipt=receipt,
    )
    portrait.data = json_safe(
        {
            **result.model_dump(),
            "last_receipt": receipt,
        }
    )
    portrait.last_receipt_payment_id = payment_id
    return portrait
