from decimal import Decimal

from pydantic import BaseModel, Field


class ChallengeOptionOut(BaseModel):
    id: str
    title: str
    description: str
    duration_days: int = Field(ge=1, le=30)
    total_steps: int = Field(ge=1, le=30)
    expected_saving: Decimal = Field(ge=0)
    markers: list[dict] = Field(default_factory=list)
    rationale: str


class ChallengeOptionsOut(BaseModel):
    proposal_id: str
    options: list[ChallengeOptionOut] = Field(min_length=1, max_length=3)


class ChallengeSelectIn(BaseModel):
    proposal_id: str
    option_id: str
