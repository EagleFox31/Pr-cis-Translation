"""Jetons de session et codes de verification d'e-mail."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    String, Boolean, Integer, DateTime, ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, new_uuid, utcnow

if TYPE_CHECKING:
    from .user import User

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id:         Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    user_id:    Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Appareil de la session : « site » ou « extension » (déconnexions séparées).
    client:     Mapped[str] = mapped_column(
        String(16), nullable=False, default="site", server_default="site",
    )

    user: Mapped[User] = relationship("User", back_populates="refresh_tokens")


# ── ExtensionAuthCode ────────────────────────────────────────────────────────

class ExtensionAuthCode(Base):
    """Code à usage unique (60 s) échangé par l'extension contre une session.

    Seule l'empreinte du code est gardée ; `code_challenge` lie le code au
    secret (PKCE) que seule l'extension qui l'a demandé connaît.
    """
    __tablename__ = "extension_auth_codes"

    id:             Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    code_hash:      Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id:        Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    code_challenge: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ── VerificationCode ─────────────────────────────────────────────────────────

class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id:         Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    user_id:    Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    code:       Mapped[str] = mapped_column(String(6), nullable=False)
    token:      Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used:       Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempts:   Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship("User", back_populates="verification_codes")
