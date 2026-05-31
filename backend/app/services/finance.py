from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Challenge, ChatMessage, Cushion, Profile, Transaction, UserFinancialPortrait, WeeklySynthesis
from app.services.serializers import money, profile_to_dict, transaction_to_dict


WEEK_DIVISOR = Decimal("4.345")


def quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def percent(done: Decimal, total: Decimal) -> int:
    if total <= 0:
        return 0
    value = int((done / total * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))
    return max(0, min(100, value))


def goal_title(profile: Profile | None) -> str:
    if not profile:
        return "начать копить"
    return (profile.custom_goal or profile.financial_goal or "начать копить").strip()


async def get_profile(session: AsyncSession, user_id: Any) -> Profile | None:
    result = await session.execute(select(Profile).where(Profile.user_id == user_id))
    return result.scalar_one_or_none()


async def get_cushion(session: AsyncSession, user_id: Any) -> Cushion | None:
    result = await session.execute(select(Cushion).where(Cushion.user_id == user_id))
    return result.scalar_one_or_none()


async def get_active_challenge(session: AsyncSession, user_id: Any) -> Challenge | None:
    result = await session.execute(
        select(Challenge)
        .where(Challenge.user_id == user_id, Challenge.status == "active")
        .order_by(Challenge.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def monthly_spent(session: AsyncSession, user_id: Any, *, category_kind: str | None = None) -> Decimal:
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    conditions = [Transaction.user_id == user_id, Transaction.purchased_at >= start]
    if category_kind:
        conditions.append(Transaction.category_kind == category_kind)
    result = await session.execute(select(func.coalesce(func.sum(Transaction.amount), 0)).where(and_(*conditions)))
    return money(result.scalar_one())


def limit_from(profile: Profile | None, cushion: Cushion | None) -> dict:
    income = money(profile.monthly_income if profile else 0)
    reserve = money(cushion.reserved_amount if cushion else 0)
    essential = money(profile.essential_monthly_expenses if profile else 0)
    debt = money(profile.static_debt_payments if profile else 0)
    monthly_available = max(Decimal("0"), income - reserve - essential - debt)
    weekly_limit = quantize(monthly_available / WEEK_DIVISOR) if monthly_available > 0 else Decimal("0")
    return {
        "weekly_limit": weekly_limit,
        "monthly_available": quantize(monthly_available),
        "formula": "доход - финансовая подушка - обязательные траты - платежи по долгам",
        "explanation": (
            f"{quantize(income)} - {quantize(reserve)} - {quantize(essential)} - {quantize(debt)} "
            f"= {quantize(monthly_available)} ₽ в месяц, или около {weekly_limit} ₽ в неделю."
        ),
    }


async def weekly_stats(session: AsyncSession, user_id: Any, weekly_limit: Decimal) -> dict:
    today = datetime.now(timezone.utc).date()
    start_day = today - timedelta(days=6)
    start_dt = datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc)
    result = await session.execute(
        select(Transaction.purchased_at, Transaction.amount).where(
            Transaction.user_id == user_id,
            Transaction.purchased_at >= start_dt,
        )
    )
    rows = result.all()
    by_day = {start_day + timedelta(days=index): Decimal("0") for index in range(7)}
    for purchased_at, amount in rows:
        day = purchased_at.date()
        if day in by_day:
            by_day[day] += money(amount)
    labels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    days = [
        {"date": day.isoformat(), "label": labels[day.weekday()], "amount": quantize(amount)}
        for day, amount in by_day.items()
    ]
    yesterday = today - timedelta(days=1)
    has_transactions = any(amount > 0 for amount in by_day.values())
    week_spent = sum(by_day.values(), Decimal("0"))
    return {
        "days": days,
        "spent_yesterday": quantize(by_day[yesterday]) if has_transactions and yesterday in by_day else None,
        "weekly_limit_remaining": quantize(max(Decimal("0"), weekly_limit - week_spent)) if has_transactions else None,
        "has_transactions": has_transactions,
    }


async def diagnosis(session: AsyncSession, user_id: Any, weekly_limit: Decimal) -> dict:
    stats = await weekly_stats(session, user_id, weekly_limit)
    spent = sum((day["amount"] for day in stats["days"]), Decimal("0"))
    if not stats["has_transactions"]:
        return {
            "status": "нужны данные",
            "summary": "Пока нет трат за последние 7 дней. Диагностика начнет работать после первых покупок.",
            "coach_question": "Давай начнем финансовую диагностику. Какие траты за неделю ты считаешь обязательными?",
            "score": 50,
        }
    load = percent(spent, weekly_limit) if weekly_limit > 0 else 100
    if load <= 70:
        status = "спокойно"
        summary = "Расходы за неделю пока укладываются в расчетный лимит."
        score = 82
    elif load <= 100:
        status = "на границе"
        summary = "Расходы близки к недельному лимиту. Есть смысл посмотреть, какие траты были гибкими."
        score = 62
    else:
        status = "перерасход"
        summary = "Расходы уже выше расчетного недельного лимита. Можно мягко разобрать, где был скачок."
        score = 38
    return {
        "status": status,
        "summary": summary,
        "coach_question": "Я посмотрел траты за неделю. Какую одну категорию ты хотел бы разобрать первой?",
        "score": score,
    }


def challenge_payload(challenge: Challenge | None) -> dict:
    if not challenge:
        return {
            "id": None,
            "state": "empty",
            "title": "Челлендж не выбран",
            "description": "",
            "progress_percent": 0,
            "completed_steps": 0,
            "total_steps": 0,
            "duration_days": 0,
            "expected_saving": Decimal("0"),
            "markers": [],
        }
    total = max(1, challenge.total_steps)
    completed = max(0, min(total, challenge.completed_steps))
    markers = challenge.markers or [{"label": str(index + 1), "completed": index < completed} for index in range(total)]
    return {
        "id": str(challenge.id),
        "state": challenge.status,
        "title": challenge.title,
        "description": challenge.description,
        "progress_percent": percent(Decimal(completed), Decimal(total)),
        "completed_steps": completed,
        "total_steps": total,
        "duration_days": challenge.duration_days,
        "expected_saving": money(challenge.expected_saving),
        "markers": markers,
    }


def transaction_detail(transaction: Transaction) -> dict:
    payload = transaction.raw_payload or {}
    item = payload.get("item") if isinstance(payload, dict) else None
    detail = transaction_to_dict(transaction)
    detail["description"] = item.get("description") if isinstance(item, dict) else None
    detail["payment_id"] = payload.get("payment_id") if isinstance(payload, dict) else None
    return detail


async def dashboard_for_user(session: AsyncSession, user: Any) -> dict:
    profile = await get_profile(session, user.id)
    cushion = await get_cushion(session, user.id)
    limit = limit_from(profile, cushion)
    stats = await weekly_stats(session, user.id, limit["weekly_limit"])
    diag = await diagnosis(session, user.id, limit["weekly_limit"])
    challenge = await get_active_challenge(session, user.id)
    target = money(profile.goal_target_amount if profile else 0)
    saved = money(profile.goal_saved_amount if profile else 0)
    goal = {
        "title": goal_title(profile),
        "target_amount": target,
        "saved_amount": saved,
        "progress_percent": percent(saved, target),
        "explanation": (
            f"Прогресс считается как накоплено / цель: {quantize(saved)} / {quantize(target)}."
            if target > 0
            else "Укажите сумму цели в анкете, чтобы прогресс считался точно."
        ),
    }
    return {
        "email": user.email,
        "profile": profile_to_dict(profile) if profile else None,
        "goal": goal,
        "stats": stats,
        "limit": limit,
        "diagnosis": diag,
        "challenge": challenge_payload(challenge),
        "monthly_income": money(profile.monthly_income if profile else 0),
        "reserved_cushion": money(cushion.reserved_amount if cushion else 0),
    }


async def financial_portrait_for_user(session: AsyncSession, user: Any) -> dict:
    profile = await get_profile(session, user.id)
    cushion = await get_cushion(session, user.id)
    limit = limit_from(profile, cushion)
    diag = await diagnosis(session, user.id, limit["weekly_limit"])

    portrait_result = await session.execute(select(UserFinancialPortrait).where(UserFinancialPortrait.user_id == user.id))
    portrait = portrait_result.scalar_one_or_none()
    tx_result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.purchased_at.desc())
        .limit(120)
    )
    transactions = list(tx_result.scalars().all())
    monthly_total = await monthly_spent(session, user.id)
    optimized = await monthly_spent(session, user.id, category_kind="optimizable")
    mandatory = money(profile.essential_monthly_expenses if profile else 0) + money(
        profile.static_debt_payments if profile else 0
    )

    category_map: dict[str, dict] = {}
    merchant_map: dict[str, dict] = {}
    for transaction in transactions:
        category = transaction.category or "Без категории"
        category_bucket = category_map.setdefault(
            category,
            {
                "name": category,
                "kind": transaction.category_kind or "unknown",
                "amount": Decimal("0"),
                "count": 0,
                "items": {},
            },
        )
        category_bucket["amount"] += money(transaction.amount)
        category_bucket["count"] += 1
        category_bucket["kind"] = transaction.category_kind or category_bucket["kind"]
        title_bucket = category_bucket["items"].setdefault(
            transaction.title,
            {"title": transaction.title, "amount": Decimal("0"), "count": 0},
        )
        title_bucket["amount"] += money(transaction.amount)
        title_bucket["count"] += 1

        merchant_bucket = merchant_map.setdefault(
            transaction.merchant,
            {"name": transaction.merchant, "amount": Decimal("0"), "count": 0},
        )
        merchant_bucket["amount"] += money(transaction.amount)
        merchant_bucket["count"] += 1

    categories = []
    for category in category_map.values():
        amount = quantize(category["amount"])
        share = percent(amount, monthly_total) if monthly_total > 0 else 0
        items = sorted(category["items"].values(), key=lambda item: item["amount"], reverse=True)[:5]
        categories.append(
            {
                "name": category["name"],
                "kind": category["kind"],
                "amount": amount,
                "count": category["count"],
                "share_percent": share,
                "items": [
                    {
                        "title": item["title"],
                        "amount": quantize(item["amount"]),
                        "count": item["count"],
                    }
                    for item in items
                ],
            }
        )
    categories.sort(key=lambda category: category["amount"], reverse=True)

    merchants = [
        {"name": merchant["name"], "amount": quantize(merchant["amount"]), "count": merchant["count"]}
        for merchant in sorted(merchant_map.values(), key=lambda merchant: merchant["amount"], reverse=True)[:8]
    ]

    portrait_data = portrait.data if portrait else {}
    summary = portrait_data.get("summary") or (
        "Портрет начнет уточняться после чеков и истории покупок. Пока показываю финансовую нагрузку по анкете и транзакциям."
    )
    return {
        "email": user.email,
        "profile": profile_to_dict(profile) if profile else None,
        "summary": summary,
        "spending_signals": portrait_data.get("spending_signals") or [],
        "psychological_hypotheses": portrait_data.get("psychological_hypotheses") or [],
        "suggested_focuses": portrait_data.get("suggested_focuses") or [],
        "metrics": {
            "monthly_income": money(profile.monthly_income if profile else 0),
            "monthly_spent": monthly_total,
            "mandatory_expenses": mandatory,
            "optimized_expenses": optimized,
            "reserved_cushion": money(cushion.reserved_amount if cushion else 0),
            "monthly_available": limit["monthly_available"],
            "weekly_limit": limit["weekly_limit"],
            "diagnosis_status": diag["status"],
            "diagnosis_score": diag["score"],
        },
        "categories": categories,
        "merchants": merchants,
        "transactions": [transaction_detail(transaction) for transaction in transactions],
    }


async def coach_context(session: AsyncSession, user_id: Any) -> dict:
    profile = await get_profile(session, user_id)
    cushion = await get_cushion(session, user_id)
    mandatory = money(profile.essential_monthly_expenses if profile else 0) + money(
        profile.static_debt_payments if profile else 0
    )
    optimized = await monthly_spent(session, user_id, category_kind="optimizable")
    spent = await monthly_spent(session, user_id)
    synthesis_result = await session.execute(
        select(WeeklySynthesis)
        .where(WeeklySynthesis.user_id == user_id)
        .order_by(WeeklySynthesis.period_end.desc())
        .limit(1)
    )
    latest = synthesis_result.scalar_one_or_none()
    portrait_result = await session.execute(select(UserFinancialPortrait).where(UserFinancialPortrait.user_id == user_id))
    portrait = portrait_result.scalar_one_or_none()
    tx_result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.purchased_at.desc())
        .limit(12)
    )
    recent_transactions = list(tx_result.scalars().all())
    income = money(profile.monthly_income if profile else 0)
    reserve = money(cushion.reserved_amount if cushion else 0)
    return {
        "profile": profile_to_dict(profile) if profile else None,
        "monthly_income": income,
        "monthly_spent": spent,
        "reserved_cushion": reserve,
        "free_after_reserve": max(Decimal("0"), income - reserve - mandatory),
        "mandatory_expenses": mandatory,
        "optimized_expenses": optimized,
        "latest_synthesis": latest.content_md if latest else None,
        "portrait": portrait.data if portrait else {},
        "recent_transactions": [transaction_to_dict(transaction) for transaction in recent_transactions],
    }


async def challenge_context(session: AsyncSession, user_id: Any) -> dict:
    context = await coach_context(session, user_id)
    context["instruction"] = (
        "Предложи до 3 добровольных микро-челленджей. "
        "Они должны опираться на психологический и финансовый портрет, анкету, лимиты и последние товары из чеков."
    )
    return context


async def recent_chat(session: AsyncSession, user_id: Any, *, limit: int = 24) -> list[ChatMessage]:
    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    messages = list(result.scalars().all())
    return list(reversed(messages))
