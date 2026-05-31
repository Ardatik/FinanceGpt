from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_cushion_token
from app.core.config import get_settings
from app.core.security import create_access_token, generate_otp, hash_secret, utcnow, verify_secret
from app.db.session import get_session
from app.models import Cushion, MagicCode, Profile, User
from app.schemas.auth import AuthCodeRequest
from app.schemas.cushion import (
    CushionRecoveryVerifyIn,
    CushionReservationIn,
    CushionSetupIn,
    CushionStateOut,
    CushionUnlockIn,
    CushionUnlockOut,
)
from app.services.emailer import send_magic_code
from app.services.finance import get_cushion, get_profile
from app.services.serializers import money


router = APIRouter()


def month_start() -> date:
    today = date.today()
    return today.replace(day=1)


async def state_payload(session: AsyncSession, user: User) -> dict:
    profile = await get_profile(session, user.id)
    cushion = await get_cushion(session, user.id)
    return {
        "is_configured": bool(cushion and cushion.code_word_hash),
        "reserved_amount": money(cushion.reserved_amount if cushion else 0),
        "monthly_income": money(profile.monthly_income if profile else 0),
        "month_start": cushion.month_start.isoformat() if cushion and cushion.month_start else None,
    }


@router.get("", response_model=CushionStateOut)
async def get_state(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await state_payload(session, current_user)


@router.post("/setup", response_model=CushionStateOut)
async def setup(
    payload: CushionSetupIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    cushion = await get_cushion(session, current_user.id)
    if not cushion:
        cushion = Cushion(user_id=current_user.id)
        session.add(cushion)
    cushion.code_word_hash = hash_secret(payload.code_word)
    cushion.month_start = cushion.month_start or month_start()
    await session.commit()
    return await state_payload(session, current_user)


@router.post("/unlock", response_model=CushionUnlockOut)
async def unlock(
    payload: CushionUnlockIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    settings = get_settings()
    cushion = await get_cushion(session, current_user.id)
    if not cushion or not cushion.code_word_hash:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Кодовое слово еще не настроено")
    if not verify_secret(payload.code_word, cushion.code_word_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Неверное кодовое слово")
    return {
        "cushion_token": create_access_token(
            current_user.id,
            minutes=settings.cushion_token_expire_minutes,
            token_type="cushion",
        ),
        "expires_in_minutes": settings.cushion_token_expire_minutes,
    }


@router.put("/reserve", response_model=CushionStateOut)
async def reserve(
    payload: CushionReservationIn,
    current_user: User = Depends(require_cushion_token),
    session: AsyncSession = Depends(get_session),
) -> dict:
    profile_result = await session.execute(select(Profile).where(Profile.user_id == current_user.id))
    profile = profile_result.scalar_one_or_none()
    monthly_income = money(profile.monthly_income if profile else 0)
    if payload.reserved_amount > monthly_income:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Резерв не может быть больше дохода")
    cushion = await get_cushion(session, current_user.id)
    if not cushion:
        cushion = Cushion(user_id=current_user.id, month_start=month_start())
        session.add(cushion)
    cushion.reserved_amount = payload.reserved_amount
    cushion.month_start = month_start()
    await session.commit()
    return await state_payload(session, current_user)


@router.post("/recovery/request")
async def recovery_request(
    payload: AuthCodeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if payload.email.lower() != current_user.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите почту аккаунта")
    code = generate_otp()
    session.add(
        MagicCode(
            email=current_user.email,
            code_hash=hash_secret(code),
            purpose="cushion_recovery",
            expires_at=utcnow() + timedelta(minutes=10),
        )
    )
    await session.commit()
    await send_magic_code(current_user.email, code, purpose="cushion_recovery")
    response = {"message": "Код восстановления отправлен на почту"}
    if get_settings().demo_mode:
        response["demo_code"] = code
    return response


@router.post("/recovery/verify", response_model=CushionStateOut)
async def recovery_verify(
    payload: CushionRecoveryVerifyIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.execute(
        select(MagicCode)
        .where(
            MagicCode.email == current_user.email,
            MagicCode.purpose == "cushion_recovery",
            MagicCode.used_at.is_(None),
            MagicCode.expires_at > utcnow(),
        )
        .order_by(MagicCode.created_at.desc())
        .limit(1)
    )
    magic_code = result.scalar_one_or_none()
    if not magic_code or not verify_secret(payload.code, magic_code.code_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный код восстановления")
    magic_code.used_at = utcnow()
    cushion = await get_cushion(session, current_user.id)
    if not cushion:
        cushion = Cushion(user_id=current_user.id, month_start=month_start())
        session.add(cushion)
    cushion.code_word_hash = hash_secret(payload.new_code_word)
    await session.commit()
    return await state_payload(session, current_user)
