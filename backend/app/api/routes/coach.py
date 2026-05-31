from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_user_from_ws_token
from app.core.prompts import COACH_STARTER_MESSAGE
from app.db.session import async_session_maker, get_session
from app.models import ChatMessage, User
from app.schemas.coach import ChatMessageOut, CoachContextOut
from app.services.ai import AIService
from app.services.finance import coach_context, recent_chat


router = APIRouter()
logger = logging.getLogger(__name__)


def msg_out(message: ChatMessage) -> dict:
    return {
        "id": str(message.id),
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
        "meta": message.meta or {},
    }


async def ensure_starter(session: AsyncSession, user: User) -> None:
    history = await recent_chat(session, user.id, limit=1)
    if history:
        return
    session.add(ChatMessage(user_id=user.id, role="assistant", content=COACH_STARTER_MESSAGE, meta={"starter": True}))
    await session.commit()


@router.get("/history", response_model=list[ChatMessageOut])
async def history(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    await ensure_starter(session, current_user)
    messages = await recent_chat(session, current_user.id, limit=100)
    return [msg_out(message) for message in messages]


@router.get("/context", response_model=CoachContextOut)
async def context(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await coach_context(session, current_user.id)


def context_as_prompt(context_payload: dict) -> str:
    portrait = json.dumps(context_payload.get("portrait") or {}, ensure_ascii=False, default=str)
    recent = json.dumps(context_payload.get("recent_transactions") or [], ensure_ascii=False, default=str)
    return (
        "Контекст пользователя из приложения FinancePay:\n"
        f"- доход за месяц: {context_payload['monthly_income']} ₽\n"
        f"- потрачено за месяц: {context_payload['monthly_spent']} ₽\n"
        f"- финансовый резерв: {context_payload['reserved_cushion']} ₽\n"
        f"- свободно после резерва и обязательных платежей: {context_payload['free_after_reserve']} ₽\n"
        f"- обязательные расходы: {context_payload['mandatory_expenses']} ₽\n"
        f"- оптимизируемые расходы: {context_payload['optimized_expenses']} ₽\n"
        f"- недельный синтез: {context_payload.get('latest_synthesis') or 'пока нет'}\n"
        f"- финансово-психологический портрет: {portrait}\n"
        f"- последние товары и транзакции: {recent}\n"
        "Не выдумывай отсутствующие данные. Если данных мало, прямо скажи об этом."
    )


@router.websocket("/ws")
async def coach_ws(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    await websocket.accept()
    if not token:
        await websocket.send_json({"type": "error", "message": "Authorization required"})
        await websocket.close(code=1008)
        return

    async with async_session_maker() as session:
        user = await get_user_from_ws_token(token, session)
        if not user:
            await websocket.send_json({"type": "error", "message": "Invalid token"})
            await websocket.close(code=1008)
            return
        ai = AIService()
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    payload = json.loads(raw)
                    text = str(payload.get("message", "")).strip()
                    meta = payload.get("meta") or {}
                except json.JSONDecodeError:
                    text = raw.strip()
                    meta = {}
                if not text:
                    await websocket.send_json({"type": "error", "message": "Пустое сообщение"})
                    continue

                user_message = ChatMessage(user_id=user.id, role="user", content=text, meta=meta)
                session.add(user_message)
                await session.commit()
                await session.refresh(user_message)
                await websocket.send_json({"type": "user_saved", "message": msg_out(user_message)})

                messages = await recent_chat(session, user.id, limit=24)
                history_messages = [
                    {"role": msg.role, "content": msg.content}
                    for msg in messages
                    if msg.role in {"user", "assistant"}
                ][-20:]
                context_payload = await coach_context(session, user.id)
                full_answer = ""
                try:
                    async for chunk in ai.stream_coach(
                        context=context_as_prompt(context_payload),
                        context_payload=context_payload,
                        history=history_messages,
                        user_message=text,
                    ):
                        full_answer += chunk
                        await websocket.send_json({"type": "token", "token": chunk})
                except Exception:
                    logger.exception("Coach websocket answer failed, using local fallback")
                    full_answer = ai.local_coach_answer(text, context_payload=context_payload)
                    await websocket.send_json({"type": "token", "token": full_answer})
                assistant_message = ChatMessage(
                    user_id=user.id,
                    role="assistant",
                    content=full_answer.strip(),
                    meta={"streamed": True},
                )
                session.add(assistant_message)
                await session.commit()
                await session.refresh(assistant_message)
                await websocket.send_json({"type": "done", "message": msg_out(assistant_message)})
        except WebSocketDisconnect:
            return
