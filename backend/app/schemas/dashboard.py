from decimal import Decimal

from pydantic import BaseModel, Field


class GoalOut(BaseModel):
    title: str
    target_amount: Decimal
    saved_amount: Decimal
    progress_percent: int
    explanation: str


class DayExpenseOut(BaseModel):
    date: str
    label: str
    amount: Decimal


class WeeklyStatsOut(BaseModel):
    days: list[DayExpenseOut]
    spent_yesterday: Decimal | None
    weekly_limit_remaining: Decimal | None
    has_transactions: bool


class LimitOut(BaseModel):
    weekly_limit: Decimal
    monthly_available: Decimal
    formula: str
    explanation: str


class DiagnosisOut(BaseModel):
    status: str
    summary: str
    coach_question: str
    score: int = Field(ge=0, le=100)


class ChallengeOut(BaseModel):
    id: str | None = None
    state: str = "empty"
    title: str
    description: str = ""
    progress_percent: int
    completed_steps: int
    total_steps: int
    duration_days: int
    expected_saving: Decimal
    markers: list[dict]


class DashboardOut(BaseModel):
    email: str
    profile: dict | None
    goal: GoalOut
    stats: WeeklyStatsOut
    limit: LimitOut
    diagnosis: DiagnosisOut
    challenge: ChallengeOut
    monthly_income: Decimal
    reserved_cushion: Decimal
