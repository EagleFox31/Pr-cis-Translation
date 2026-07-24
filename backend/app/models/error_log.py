"""Journal central des erreurs.

Une ligne = UNE occurrence d'erreur, d'où qu'elle vienne : rendu React, appel
réseau, exception backend, thread de traduction. On écrit TOUT — un journal qui
trie à l'entrée est un journal qui ment le jour où le défaut est justement dans
ce qu'il a écarté.

REGROUPEMENT
    `fingerprint` est un hash stable (source + niveau + message + localisation).
    Deux occurrences du même bug le partagent : la vue admin les empile sous une
    seule entrée (« TypeError … ×12 »), au lieu de noyer l'œil sous les doublons.

CYCLE DE VIE
    `status` va de `new` à `handled`. On ne SUPPRIME que du `handled` : l'admin
    doit d'abord consigner (exporter) puis marquer traité. Sans ce garde-fou, un
    coup d'éponge effacerait des erreurs jamais lues.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_uuid, utcnow

# Vocabulaire fermé, gardé en clair côté application (pas d'ENUM SQL : ajouter
# une valeur ne doit pas imposer une migration de type).
SOURCES = ("frontend", "backend", "api")
LEVELS = ("error", "warning", "critical")
STATUS_NEW = "new"
STATUS_HANDLED = "handled"


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)

    source: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="error", index=True)

    message: Mapped[str] = mapped_column(Text, nullable=False)
    stack: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Route, méthode, statut HTTP, URL, composant, user-agent, extras… tout ce qui
    # aide à reproduire, sans schéma figé (une erreur front et une erreur backend
    # n'ont pas le même contexte utile).
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # L'utilisateur au moment de l'erreur. `user_id` peut pointer un compte
    # supprimé depuis : on garde donc AUSSI l'e-mail en clair (`SET NULL` sur la
    # FK n'efface pas le snapshot), pour ne pas perdre « qui » après coup.
    user_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Hash de regroupement (source+level+message+localisation). Indexé : la vue
    # admin agrège dessus, et le compteur d'occurrences se lit d'un GROUP BY.
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False,
                                        default=STATUS_NEW, index=True)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True,
    )
