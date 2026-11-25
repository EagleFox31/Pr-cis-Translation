"""Compteurs permanents de l'extension, par utilisateur et par page."""
from __future__ import annotations

from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class ExtensionUsage(Base):
    """Ce qu'une page (identifiant opaque `X-Page`) a déjà fait traduire.

    Les compteurs ne se remettent jamais à zéro : une page qui a atteint la
    limite de son forfait ne repart pas en attendant. `jour` (UTC) est celui de
    la première traduction : il sert à compter les pages commencées dans la
    journée.
    """
    __tablename__ = "extension_usage"
    __table_args__ = (Index("ix_extension_usage_jour", "user_id", "jour"),)

    user_id:    Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    page:       Mapped[str] = mapped_column(String(64), primary_key=True)
    caracteres: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    images:     Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jour:       Mapped[date] = mapped_column(Date, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,
                                                 onupdate=utcnow)


class ExtensionTexteVu(Base):
    """Empreinte d'un texte déjà compté pour ce compte (SHA-256 du compte, de la
    langue et du texte) : ni le texte ni sa traduction ne sont gardés. Revu par
    le même compte, le texte n'est plus compté. Effacée après 30 jours."""
    __tablename__ = "extension_textes_vus"
    __table_args__ = (Index("ix_extension_textes_vus_jour", "jour"),)

    user_id:   Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    empreinte: Mapped[str] = mapped_column(String(64), primary_key=True)
    jour:      Mapped[date] = mapped_column(Date, nullable=False)
