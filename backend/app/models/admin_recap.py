"""Registre des récapitulatifs quotidiens envoyés aux admins : un par jour.

La clé primaire sur le jour rend l'envoi idempotent : un redémarrage, ou deux
processus qui tournent en même temps, n'envoient jamais deux fois le même jour.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class AdminRecap(Base):
    __tablename__ = "admin_recaps"

    jour: Mapped[date] = mapped_column(Date, primary_key=True)
    envoye_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow,
    )
