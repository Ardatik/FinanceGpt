from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime
    meta: dict = Field(default_factory=dict)


class CoachContextOut(BaseModel):
    profile: dict | None = None
    monthly_income: Decimal
    monthly_spent: Decimal
    reserved_cushion: Decimal
    free_after_reserve: Decimal
    mandatory_expenses: Decimal
    optimized_expenses: Decimal
    latest_synthesis: str | None = None
    portrait: dict = Field(default_factory=dict)
    recent_transactions: list[dict] = Field(default_factory=list)
