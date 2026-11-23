"""Durable authenticated Payment Orchestrator event receipt, NOT a credit grant."""
from __future__ import annotations

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class OrchestratorPaymentEvent(Base):
    __tablename__ = "payment_orchestrator_events"
    __table_args__ = (
        UniqueConstraint("project_id", "environment", "effect_key",
                         name="uq_orchestrator_payment_effect"),
    )

    event_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(8), nullable=False)
    effect_key: Mapped[str] = mapped_column(String(160), nullable=False)
    payment_id: Mapped[str] = mapped_column(String(160), nullable=False)
    merchant_id: Mapped[str] = mapped_column(String(160), nullable=False)
    external_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    # No business effect until a local, server-created payment/quote is matched.
    state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="pending_purchase_match"
    )
    received_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
