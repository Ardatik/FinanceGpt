from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, decode_token, generate_otp, hash_secret, utcnow, verify_secret
from app.db.session import get_session
from app.models import MagicCode, User
from app.schemas.auth import AuthCodeRequest, AuthRefreshRequest, AuthVerifyRequest, TokenResponse
from app.services.emailer import send_magic_code


router = APIRouter()


def user_out(user: User) -> dict:
    return {"id": str(user.id), "email": user.email, "onboarding_completed": user.onboarding_completed}


def token_pair(user: User) -> dict:
    settings = get_settings()
    return {
        "access_token": create_access_token(
            user.id,
            minutes=settings.access_token_expire_minutes,
            token_type="access",
        ),
        "refresh_token": create_access_token(
            user.id,
            minutes=settings.refresh_token_expire_minutes,
            token_type="refresh",
        ),
        "expires_in": settings.access_token_expire_minutes * 60,
        "user": user_out(user),
    }


@router.post("/request-code")
async def request_code(payload: AuthCodeRequest, session: AsyncSession = Depends(get_session)) -> dict:
    code = generate_otp()
    session.add(
        MagicCode(
            email=payload.email.lower(),
            code_hash=hash_secret(code),
            purpose="login",
            expires_at=utcnow() + timedelta(minutes=10),
        )
    )
    await session.commit()
    await send_magic_code(payload.email, code, purpose="login")
    return {"message": "Код отправлен на почту"}


@router.post("/verify", response_model=TokenResponse)
async def verify_code(payload: AuthVerifyRequest, session: AsyncSession = Depends(get_session)) -> dict:
    email = payload.email.lower()
    result = await session.execute(
        select(MagicCode)
        .where(
            MagicCode.email == email,
            MagicCode.purpose == "login",
            MagicCode.used_at.is_(None),
            MagicCode.expires_at > utcnow(),
        )
        .order_by(MagicCode.created_at.desc())
        .limit(1)
    )
    magic_code = result.scalar_one_or_none()
    if not magic_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Код не найден или истек")
    if magic_code.attempts >= 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Слишком много попыток")
    magic_code.attempts += 1
    if not verify_secret(payload.code, magic_code.code_hash):
        await session.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный код")

    magic_code.used_at = datetime.now(timezone.utc)
    user_result = await session.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    if not user:
        user = User(email=email)
        session.add(user)
        await session.flush()
    user.last_login_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(user)
    return token_pair(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: AuthRefreshRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        decoded = decode_token(payload.refresh_token, expected_type="refresh")
        user_id = UUID(decoded["sub"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return token_pair(user)


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)) -> dict:
    return user_out(current_user)
