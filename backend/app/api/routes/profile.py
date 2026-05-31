from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import Profile, User
from app.schemas.profile import ProfileIn, ProfileOut
from app.services.serializers import json_safe, profile_to_dict


router = APIRouter()


@router.get("", response_model=ProfileOut | None)
async def get_profile(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict | None:
    result = await session.execute(select(Profile).where(Profile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    return profile_to_dict(profile) if profile else None


@router.put("", response_model=ProfileOut)
async def upsert_profile(
    payload: ProfileIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.execute(select(Profile).where(Profile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    data = payload.model_dump()
    data["fixed_expenses"] = json_safe(data["fixed_expenses"])
    if not profile:
        profile = Profile(user_id=current_user.id, **data)
        session.add(profile)
    else:
        for key, value in data.items():
            setattr(profile, key, value)
    current_user.onboarding_completed = True
    await session.commit()
    await session.refresh(profile)
    return profile_to_dict(profile)
