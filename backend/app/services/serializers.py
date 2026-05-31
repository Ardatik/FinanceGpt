from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


def money(value: Decimal | int | float | None) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def profile_to_dict(profile: Any) -> dict:
    return {
        "id": str(profile.id),
        "user_id": str(profile.user_id),
        "name": profile.name,
        "gender": profile.gender,
        "age": profile.age,
        "city": profile.city,
        "monthly_income": money(profile.monthly_income),
        "income_bucket": profile.income_bucket,
        "income_sources": profile.income_sources or [],
        "family_status": profile.family_status,
        "debt_status": profile.debt_status,
        "situation": profile.situation,
        "financial_goal": profile.financial_goal,
        "custom_goal": profile.custom_goal,
        "goal_target_amount": money(profile.goal_target_amount),
        "goal_saved_amount": money(profile.goal_saved_amount),
        "goal_due_date": profile.goal_due_date,
        "fixed_expenses": profile.fixed_expenses or {},
        "essential_monthly_expenses": money(profile.essential_monthly_expenses),
        "static_debt_payments": money(profile.static_debt_payments),
        "wants_challenges": profile.wants_challenges,
    }


def transaction_to_dict(transaction: Any) -> dict:
    return {
        "id": str(transaction.id),
        "source": transaction.source,
        "merchant": transaction.merchant,
        "title": transaction.title,
        "amount": money(transaction.amount),
        "quantity": money(transaction.quantity),
        "unit_price": money(transaction.unit_price),
        "purchased_at": transaction.purchased_at,
        "category": transaction.category,
        "category_kind": transaction.category_kind,
        "impulse_type": transaction.impulse_type,
    }


def payment_to_dict(payment: Any) -> dict:
    return {
        "id": str(payment.id),
        "bank": payment.bank,
        "amount": money(payment.amount),
        "merchant": payment.merchant,
        "status": payment.status,
        "deeplink": payment.deeplink,
        "fallback_url": payment.fallback_url,
        "external_payload": payment.external_payload or {},
    }
