from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    gender: str | None = None
    age: int | None = Field(default=None, ge=14, le=100)
    city: str | None = None
    monthly_income: Decimal = Field(default=0, ge=0)
    income_bucket: str | None = None
    income_sources: list[str] = Field(default_factory=list)
    family_status: str | None = None
    debt_status: str | None = None
    situation: str | None = None
    financial_goal: str = Field(default="начать копить", min_length=1, max_length=255)
    custom_goal: str | None = Field(default=None, max_length=255)
    goal_target_amount: Decimal = Field(default=0, ge=0)
    goal_saved_amount: Decimal = Field(default=0, ge=0)
    goal_due_date: date | None = None
    fixed_expenses: dict[str, Decimal] = Field(default_factory=dict)
    essential_monthly_expenses: Decimal = Field(default=0, ge=0)
    static_debt_payments: Decimal = Field(default=0, ge=0)
    wants_challenges: bool = True


class ProfileOut(ProfileIn):
    id: str
    user_id: str
