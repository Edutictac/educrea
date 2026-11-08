"""Sandbox ledger. Never mixed with included AI credits or provider budgets."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from ..db import Base
from .entities import utcnow


class TestTopup(Base):
    __tablename__ = "billing_test_topups"
    __table_args__ = (UniqueConstraint("user_id", "request_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    request_id: Mapped[UUID] = mapped_column(Uuid)
    session_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    checkout_url: Mapped[str | None] = mapped_column(String(2048))
    return_base: Mapped[str] = mapped_column(String(500))
    state: Mapped[str] = mapped_column(String(20), default="creating")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TestWalletEntry(Base):
    __tablename__ = "billing_test_entries"
    __table_args__ = (CheckConstraint("amount_microeur = 10000000", name="ck_test_topup_amount"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    topup_id: Mapped[UUID] = mapped_column(ForeignKey("billing_test_topups.id"), unique=True)
    amount_microeur: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
