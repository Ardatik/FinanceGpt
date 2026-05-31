from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models import ChatMessage, Transaction, User, WeeklySynthesis
from app.services.ai import AIService
from app.services.serializers import transaction_to_dict


async def run_weekly_synthesis(sessionmaker: async_sessionmaker) -> None:
    ai = AIService()
    now = datetime.now(timezone.utc)
    period_end = now.date()
    period_start = (now - timedelta(days=7)).date()
    start_dt = datetime.combine(period_start, datetime.min.time(), tzinfo=timezone.utc)

    async with sessionmaker() as session:
        users = (await session.execute(select(User).where(User.is_active.is_(True)))).scalars().all()
        for user in users:
            txs = (
                await session.execute(
                    select(Transaction)
                    .where(Transaction.user_id == user.id, Transaction.purchased_at >= start_dt)
                    .order_by(Transaction.purchased_at.asc())
                )
            ).scalars().all()
            messages = (
                await session.execute(
                    select(ChatMessage)
                    .where(ChatMessage.user_id == user.id, ChatMessage.created_at >= start_dt)
                    .order_by(ChatMessage.created_at.asc())
                )
            ).scalars().all()
            payload = {
                "transactions": [transaction_to_dict(tx) for tx in txs],
                "messages": [{"role": msg.role, "content": msg.content} for msg in messages[-40:]],
            }
            synthesis = await ai.weekly_synthesis(payload=payload)
            session.add(
                WeeklySynthesis(
                    user_id=user.id,
                    period_start=period_start,
                    period_end=period_end,
                    content_md=synthesis.summary_md,
                    data={
                        "patterns": synthesis.patterns,
                        "suggested_challenge": synthesis.suggested_challenge,
                        "risk_level": synthesis.risk_level,
                    },
                )
            )
        await session.commit()
