"""Traces anti-abus des pages offertes : liens d'appareil et attributions.

Uniquement des empreintes HMAC, jamais d'adresse IP ni de valeur brute. Les deux
tables sont purgées automatiquement (`app.services.anti_abus.purge`) : les
liens après 60 jours sans activité, les attributions après 35 jours.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_uuid, utcnow


class DeviceLink(Base):
    """Un identifiant d'appareil (cookie, copie locale, empreinte) rattaché à une machine.

    Plusieurs liens peuvent pointer vers la même `machine_id` : c'est ainsi
    qu'un cookie effacé est retrouvé par l'empreinte, et inversement.
    """
    __tablename__ = "device_links"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # cookie | copy | print
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    machine_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,
                                                 nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,
                                                nullable=False, index=True)


class FreeGrant(Base):
    """Pages offertes réellement attribuées à un compte, avec les signaux du moment."""
    __tablename__ = "free_grants"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    machine_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # HMAC de la boîte e-mail canonique (alias +tag, points Gmail…).
    mailbox_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pages: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,
                                                 nullable=False)

    __table_args__ = (
        Index("ix_free_grants_machine_recent", "machine_id", "created_at"),
        Index("ix_free_grants_ip_recent", "ip_hash", "created_at"),
        Index("ix_free_grants_mailbox_recent", "mailbox_key", "created_at"),
        Index("ix_free_grants_created_at", "created_at"),
    )
