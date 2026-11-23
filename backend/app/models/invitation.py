"""Invitations envoyées par les utilisateurs à découvrir Précis.

POURQUOI UNE TABLE, ET PAS UN SIMPLE ENVOI
    N'importe quel compte peut faire partir un e-mail vers une adresse qu'il
    choisit, depuis NOTRE domaine. Sans trace, rien n'empêche d'en faire un
    canon à spam — et c'est notre réputation d'expéditeur qui brûle, donc nos
    codes de connexion qui finissent en indésirables. La table sert de garde :
    quota quotidien par compte, et pas deux invitations à la même adresse dans
    une fenêtre courte, qui qu'en soit l'auteur.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_uuid, utcnow


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)

    # L'auteur. SET NULL : supprimer un compte ne doit pas effacer la trace qui
    # garde l'adresse invitée de recevoir un second e-mail trop tôt.
    inviter_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    # Normalisée (minuscules, sans espaces) : c'est la clé de l'anti-doublon.
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True,
    )
