"""
Modèles SQLAlchemy — User, Document, RefreshToken, VerificationCode.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String, Boolean, BigInteger, Integer, DateTime, Enum, ForeignKey, Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


# ── Plans & quotas ───────────────────────────────────────────────────────────

PLAN_STORAGE: dict[str, int] = {
    "free":       0,              # traduction seule, pas de stockage
    "starter":    524_288_000,    # 500 Mo
    "pro":        2_147_483_648,  # 2 Go
    "enterprise": 10_737_418_240, # 10 Go
    "admin":      10_737_418_240, # 10 Go (affiche « illimité »)
}

# Nombre MAX de pages traduisibles (None = illimité)
PLAN_PAGE_LIMIT: dict[str, int | None] = {
    "free":       1,
    "starter":    None,
    "pro":        None,
    "enterprise": None,
    "admin":      None,
}

def get_plan_page_limit(plan: str) -> int | None:
    """Retourne la limite de pages pour un plan, None = illimité."""
    return PLAN_PAGE_LIMIT.get(plan, 1)  # défaut = 1 page (freemium)

# Le SEUL plan sans droits (ni téléchargement, ni aperçu en clair). On nomme
# l'exception plutôt que d'énumérer les plans payants : ajouter un plan ne doit
# pas obliger à penser à l'inscrire ici. Miroir de `frontend/src/lib/plans.ts`.
FREE_PLAN = "free"

def is_paid_plan(plan: str | None) -> bool:
    """Le plan donne-t-il les droits complets ?"""
    return bool(plan) and plan != FREE_PLAN

PLAN_LABELS: dict[str, str] = {
    "free":       "Gratuit",
    "starter":    "Starter",
    "pro":        "Pro",
    "enterprise": "Enterprise",
    "admin":      "Admin",
}

def get_plan_storage(plan: str) -> int:
    """Retourne la limite de stockage pour un plan donné, 0 par défaut."""
    return PLAN_STORAGE.get(plan, 0)


# ── User ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id:            Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_uuid)
    email:         Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name:          Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    google_id:     Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    avatar_url:    Mapped[str | None] = mapped_column(String(512), nullable=True)
    plan:          Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    storage_used:  Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    storage_limit: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at:    Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
    )

    documents: Mapped[list[Document]] = relationship(
        "Document", back_populates="user", cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan",
    )
    verification_codes: Mapped[list[VerificationCode]] = relationship(
        "VerificationCode", back_populates="user", cascade="all, delete-orphan",
    )


# ── Document ─────────────────────────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"

    id:              Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_uuid)
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
    created_at:      Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at:      Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
    )

    user: Mapped[User] = relationship("User", back_populates="documents")


# ── RefreshToken ─────────────────────────────────────────────────────────────

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id:         Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_uuid)
    user_id:    Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped[User] = relationship("User", back_populates="refresh_tokens")


# ── VerificationCode ─────────────────────────────────────────────────────────

class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id:         Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_uuid)
    user_id:    Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    code:       Mapped[str] = mapped_column(String(6), nullable=False)
    token:      Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used:       Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempts:   Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped[User] = relationship("User", back_populates="verification_codes")
