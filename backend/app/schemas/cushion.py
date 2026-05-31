from decimal import Decimal

from pydantic import BaseModel, Field


class CushionSetupIn(BaseModel):
    code_word: str = Field(min_length=4, max_length=80)


class CushionUnlockIn(BaseModel):
    code_word: str = Field(min_length=4, max_length=80)


class CushionUnlockOut(BaseModel):
    cushion_token: str
    expires_in_minutes: int


class CushionReservationIn(BaseModel):
    reserved_amount: Decimal = Field(ge=0)


class CushionRecoveryVerifyIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    new_code_word: str = Field(min_length=4, max_length=80)


class CushionStateOut(BaseModel):
    is_configured: bool
    reserved_amount: Decimal
    monthly_income: Decimal
    month_start: str | None
