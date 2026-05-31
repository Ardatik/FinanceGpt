from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import Challenge, ChatMessage, User
from app.schemas.challenge import ChallengeOptionsOut, ChallengeSelectIn
from app.schemas.dashboard import ChallengeOut
from app.services.ai import AIService
from app.services.finance import challenge_context, challenge_payload, get_active_challenge
from app.services.serializers import json_safe


router = APIRouter()


@router.post("/options", response_model=ChallengeOptionsOut)
async def challenge_options(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    context = await challenge_context(session, current_user.id)
    result = await AIService().challenge_options(context=context)
    options = json_safe([option.model_dump() for option in result.options[:3]])
    if not options:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Не удалось подготовить челленджи")

    proposal = ChatMessage(
        user_id=current_user.id,
        role="assistant",
        content="Я подготовил несколько вариантов челленджа. Выбор остается за тобой.",
        meta={"type": "challenge_options", "options": options, "source": "ai_coach"},
    )
    session.add(proposal)
    await session.commit()
    await session.refresh(proposal)
    return {"proposal_id": str(proposal.id), "options": options}


@router.post("/select", response_model=ChallengeOut)
async def select_challenge(
    payload: ChallengeSelectIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        proposal_id = UUID(payload.proposal_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный proposal_id") from exc

    proposal = await session.get(ChatMessage, proposal_id)
    if (
        not proposal
        or proposal.user_id != current_user.id
        or (proposal.meta or {}).get("type") != "challenge_options"
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Варианты челленджа не найдены")

    options = (proposal.meta or {}).get("options") or []
    selected = next((option for option in options if option.get("id") == payload.option_id), None)
    if not selected:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Такой вариант челленджа не найден")

    active = await get_active_challenge(session, current_user.id)
    if active:
        active.status = "archived"

    total_steps = int(selected.get("total_steps") or selected.get("duration_days") or 7)
    duration_days = int(selected.get("duration_days") or total_steps)
    markers = selected.get("markers") or [{"label": str(index + 1), "completed": False} for index in range(total_steps)]
    now = datetime.now(timezone.utc).date()
    challenge = Challenge(
        user_id=current_user.id,
        title=selected["title"],
        description=selected.get("description") or "",
        total_steps=total_steps,
        completed_steps=0,
        expected_saving=Decimal(str(selected.get("expected_saving") or 0)),
        duration_days=duration_days,
        starts_at=now,
        ends_at=now + timedelta(days=duration_days),
        status="active",
        markers=markers,
    )
    session.add(challenge)
    await session.commit()
    await session.refresh(challenge)
    return challenge_payload(challenge)
