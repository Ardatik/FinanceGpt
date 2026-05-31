from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ManualTransactionIn(BaseModel):
    merchant: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0)
    category: str | None = None
    category_kind: str | None = None
    purchased_at: datetime | None = None


class TransactionOut(BaseModel):
    id: str
    source: str
    merchant: str
    title: str
    amount: Decimal
    quantity: Decimal
    unit_price: Decimal
    purchased_at: datetime
    category: str | None
    category_kind: str | None
    impulse_type: str | None
