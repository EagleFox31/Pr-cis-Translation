"""Historique des forfaits d'un compte.

`User.plan` ne dit que le plan du moment. Chaque changement laisse ici une
ligne : achat, renouvellement, attribution par l'administration, échéance.
L'inscription n'y figure pas : la fiche d'administration la date par
`User.created_at` (docs/etude-historique-forfaits.md).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_uuid, utcnow

EVENT_SUBSCRIPTION = "subscription"
EVENT_RENEWAL = "renewal"
EVENT_ADMIN = "admin"
EVENT_EXPIRY = "expiry"


class PlanEvent(Base):
    __tablename__ = "plan_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    # Plan en vigueur APRÈS l'événement (`free` pour une échéance).
    plan: Mapped[str] = mapped_column(String(20), nullable=False)
    months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True,
    )
    # Date de l'événement : pour une échéance, le jour où le plan a pris fin.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,
                                                 nullable=False)
