"""Document envoye et sa traduction."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    String, Boolean, BigInteger, Integer, DateTime, ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, new_uuid, utcnow

if TYPE_CHECKING:
    from .user import User

class Document(Base):
    __tablename__ = "documents"

    id:              Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    user_id:         Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    original_name:   Mapped[str] = mapped_column(String(512), nullable=False)
    source_lang:     Mapped[str] = mapped_column(String(10), nullable=False)
    target_lang:     Mapped[str] = mapped_column(String(10), nullable=False)
    original_path:   Mapped[str] = mapped_column(String(1024), nullable=False)
    translated_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    size_bytes:      Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Ce qui a été DÉBITÉ de `User.storage_used` à la création (0 si quota
    # plein ou plan sans stockage). La suppression rembourse cette valeur —
    # rembourser `size_bytes` faisait dériver le compteur sous la réalité.
    storage_charged: Mapped[int] = mapped_column(BigInteger, default=0,
                                                 nullable=False)
    status:          Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    page_count:      Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Pages TERMINÉES. Persisté, et non gardé en mémoire : l'avancement doit
    # être lisible par une autre session que celle qui a lancé la traduction,
    # et survivre à une reconnexion comme à un redémarrage du serveur.
    pages_done:      Mapped[int] = mapped_column(Integer, default=0,
                                                 nullable=False)
    # Ce document a-t-il été PAYÉ ? Le droit de télécharger et de voir en clair
    # se lisait jusqu'ici sur le PLAN (`is_paid_plan`), ce qui interdisait à un
    # compte Gratuit de récupérer quoi que ce soit — y compris ce qu'il venait
    # d'acheter à la page. Le droit appartient au DOCUMENT : un compte Gratuit
    # a exactement ce qu'il a payé, ni plus, ni moins.
    paid:            Mapped[bool] = mapped_column(Boolean, default=False,
                                                  nullable=False)
    created_at:      Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at:      Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow,
    )

    user: Mapped[User] = relationship("User", back_populates="documents")
