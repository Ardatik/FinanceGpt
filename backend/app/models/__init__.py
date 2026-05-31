from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped["Profile | None"] = relationship(back_populates="user", cascade="all, delete-orphan")
    cushion: Mapped["Cushion | None"] = relationship(back_populates="user", cascade="all, delete-orphan")


class MagicCode(TimestampMixin, Base):
    __tablename__ = "magic_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), default="login", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(60))
    age: Mapped[int | None] = mapped_column(Integer)
    city: Mapped[str | None] = mapped_column(String(120))
    monthly_income: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    income_bucket: Mapped[str | None] = mapped_column(String(80))
    income_sources: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    family_status: Mapped[str | None] = mapped_column(String(120))
    debt_status: Mapped[str | None] = mapped_column(String(120))
    situation: Mapped[str | None] = mapped_column(String(160))
    financial_goal: Mapped[str] = mapped_column(String(255), default="начать копить", nullable=False)
    custom_goal: Mapped[str | None] = mapped_column(String(255))
    goal_target_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    goal_saved_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    goal_due_date: Mapped[date | None] = mapped_column(Date)
    fixed_expenses: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    essential_monthly_expenses: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    static_debt_payments: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    wants_challenges: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped[User] = relationship(back_populates="profile")


class Cushion(TimestampMixin, Base):
    __tablename__ = "cushions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    code_word_hash: Mapped[str | None] = mapped_column(String(255))
    reserved_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    month_start: Mapped[date | None] = mapped_column(Date)

    user: Mapped[User] = relationship(back_populates="cushion")


class MailIntegration(TimestampMixin, Base):
    __tablename__ = "mail_integrations"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_mail_provider_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), default="mailru", nullable=False)
    mailbox_email: Mapped[str | None] = mapped_column(String(320))
    access_token: Mapped[str | None] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
    merchant: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=1, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    category: Mapped[str | None] = mapped_column(String(120))
    category_kind: Mapped[str | None] = mapped_column(String(40))
    impulse_type: Mapped[str | None] = mapped_column(String(80))
    optimized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    bank: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    merchant: Mapped[str] = mapped_column(String(255), default='ООО "Яндекс Маркет"', nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="created", nullable=False)
    deeplink: Mapped[str | None] = mapped_column(Text)
    fallback_url: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class ChatMessage(TimestampMixin, Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class WeeklySynthesis(TimestampMixin, Base):
    __tablename__ = "weekly_syntheses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class UserFinancialPortrait(TimestampMixin, Base):
    __tablename__ = "user_financial_portraits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    last_receipt_payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class Challenge(TimestampMixin, Base):
    __tablename__ = "challenges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    total_steps: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    completed_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expected_saving: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    starts_at: Mapped[date | None] = mapped_column(Date)
    ends_at: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    markers: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
