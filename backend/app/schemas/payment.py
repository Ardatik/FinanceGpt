from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentStartIn(BaseModel):
    bank: str = Field(pattern="^(sber|vtb|alfa|tbank)$")
    amount: Decimal = Field(gt=0)
    merchant: str = 'ООО "Яндекс Маркет"'
    qr_payload: str | None = Field(default=None, max_length=4096)


class PaymentQrRequestIn(BaseModel):
    bank: str = Field(default="sber", pattern="^(sber|vtb|alfa|tbank)$")
    qr_payload: str = Field(min_length=1, max_length=4096)
    amount_hint: Decimal | None = Field(default=None, ge=0)


class PaymentMockItem(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    amount: Decimal = Field(ge=0)


class PaymentMockCallbackIn(BaseModel):
    payment_id: UUID
    merchant: str = Field(min_length=1, max_length=255)
    items: list[PaymentMockItem] = Field(min_length=1)
    total_amount: Decimal = Field(ge=0)
    status: str = "confirmed"
    paid_at: datetime | None = None


class PaymentOut(BaseModel):
    id: str
    bank: str
    amount: Decimal
    merchant: str
    status: str
    deeplink: str | None
    fallback_url: str | None
    external_payload: dict
