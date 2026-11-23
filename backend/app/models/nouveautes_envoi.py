"""Registre des e-mails « Nouveautés » envoyés : un par compte et par version.

La contrainte d'unicité rend l'envoi idempotent : relancer le script d'une
version déjà partie n'écrit à personne une seconde fois.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_uuid, utcnow


class NouveauteEnvoi(Base):
    __tablename__ = "nouveautes_envois"
    __table_args__ = (
        UniqueConstraint("user_id", "version", name="uq_nouveautes_envois_user_version"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    envoye_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow,
    )
