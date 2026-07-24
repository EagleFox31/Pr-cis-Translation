"""Demandes d'assistance envoyées par les utilisateurs.

Deux besoins, un seul objet : SIGNALER un problème, et demander de l'aide sur son
ABONNEMENT. La `category` les distingue ; le reste est commun (sujet, message,
qui, quand, contexte).

Frère du journal d'erreurs (`error_log.py`) mais DISTINCT : le journal capte ce
que la machine constate ; ici c'est ce qu'un HUMAIN prend la peine d'écrire. Ne
jamais mélanger les deux — un ticket de support n'a pas de `fingerprint`, et une
erreur JS n'a pas de sujet rédigé.

CYCLE DE VIE
    `status` va de `open` à `handled`. On ne SUPPRIME que du `handled` : une
    demande ouverte est quelqu'un qui attend encore une réponse.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_uuid, utcnow

# Vocabulaire fermé, gardé en clair côté application (pas d'ENUM SQL).
CATEGORIES = ("problem", "subscription", "other")
STATUS_OPEN = "open"
STATUS_HANDLED = "handled"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)

    category: Mapped[str] = mapped_column(String(16), nullable=False,
                                          default="problem", index=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Page d'où part la demande, plan au moment T, user-agent… ce qui aide à
    # répondre sans schéma figé.
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # L'auteur. `user_id` peut pointer un compte supprimé depuis (SET NULL) : on
    # garde AUSSI l'e-mail en clair pour savoir à qui répondre après coup.
    user_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False,
                                        default=STATUS_OPEN, index=True)
    # Note interne de l'admin (ce qui a été fait / répondu). Jamais montrée à
    # l'utilisateur : c'est un pense-bête de traitement, pas une réponse publique.
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True,
    )
