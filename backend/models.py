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
    "starter":    2_147_483_648,  # 2 Go
    "pro":        21_474_836_480, # 20 Go
    "enterprise": 214_748_364_800,# 200 Go
    "admin":      214_748_364_800,# 200 Go (affiche « illimité »)
}

# ATTENTION — deux plafonds DIFFÉRENTS, longtemps confondus sous un seul nom.
#
#  • PLAN_PAGE_LIMIT   : combien de pages au maximum dans UN SEUL document.
#                        C'est ce que `cap_pages_for_plan` tronque à l'envoi.
#  • PLAN_MONTHLY_PAGES: combien de pages au total sur un MOIS calendaire.
#                        C'est le quota commercial affiché sur la carte.
#
# Les mélanger, c'était vendre « 100 pages par mois » et livrer « 100 pages par
# document, autant de fois que vous voulez ». La valeur `None` signifie « pas de
# plafond de ce type ».

PLAN_PAGE_LIMIT: dict[str, int | None] = {
    "free":       1,      # l'essai porte sur une page, et une seule
    "starter":    None,
    "pro":        None,
    "enterprise": None,
    "admin":      None,
}

PLAN_MONTHLY_PAGES: dict[str, int | None] = {
    "free":       1,      # 1 page offerte / mois, puis paiement à la page
    "starter":    100,
    "pro":        500,
    "enterprise": None,   # illimité, cadré par contrat
    "admin":      None,
}

def get_plan_page_limit(plan: str) -> int | None:
    """Pages max dans UN document pour ce plan. None = pas de plafond."""
    return PLAN_PAGE_LIMIT.get(plan, 1)  # défaut = 1 page (freemium)

def get_plan_monthly_pages(plan: str) -> int | None:
    """Pages max sur le MOIS pour ce plan. None = illimité."""
    return PLAN_MONTHLY_PAGES.get(plan, 1)

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
    # Pages achetées à l'unité et pas encore consommées (forfait Gratuit).
    # C'est un SOLDE, pas un historique : il est débité au lancement d'une
    # traduction, et les paiements qui l'ont alimenté vivent dans `payments`.
    page_credits:  Mapped[int] = mapped_column(Integer, default=0, nullable=False)
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
    # Ce document a-t-il été PAYÉ ? Le droit de télécharger et de voir en clair
    # se lisait jusqu'ici sur le PLAN (`is_paid_plan`), ce qui interdisait à un
    # compte Gratuit de récupérer quoi que ce soit — y compris ce qu'il venait
    # d'acheter à la page. Le droit appartient au DOCUMENT : un compte Gratuit
    # a exactement ce qu'il a payé, ni plus, ni moins.
    paid:            Mapped[bool] = mapped_column(Boolean, default=False,
                                                  nullable=False)
    created_at:      Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at:      Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
    )

    user: Mapped[User] = relationship("User", back_populates="documents")


# ── Payment ──────────────────────────────────────────────────────────────────

class Payment(Base):
    """Une tentative d'encaissement. Y compris celles qui échouent.

    On enregistre AVANT d'appeler le fournisseur, jamais après : un paiement
    dont la trace n'existe qu'en cas de succès est un paiement qu'on ne saura
    pas réconcilier le jour où le réseau coupe entre l'encaissement et la
    réponse. Le client a été débité ; nous, nous n'en saurions rien.
    """
    __tablename__ = "payments"

    id:       Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_uuid)
    user_id:  Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    # Paiement d'un document précis (débloquer un téléchargement) ou achat de
    # pages d'avance (`None`).
    document_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True,
    )
    pages:    Mapped[int] = mapped_column(Integer, nullable=False)
    # Montant en unités MINEURES, tel qu'envoyé au fournisseur. On garde aussi
    # la devise et la zone : un litige six mois plus tard se tranche sur ce qui
    # a été facturé ce jour-là, pas sur la grille en vigueur aujourd'hui.
    amount:   Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    zone:     Mapped[str] = mapped_column(String(2), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), default="campay", nullable=False)
    # Référence rendue par le fournisseur — la clé de réconciliation.
    provider_ref: Mapped[str | None] = mapped_column(String(128), nullable=True,
                                                     unique=True, index=True)
    # PENDING · SUCCESSFUL · FAILED — vocabulaire de Campay, gardé tel quel
    # pour qu'un état lu dans nos logs se retrouve dans leur tableau de bord.
    status:   Mapped[str] = mapped_column(String(20), default="PENDING",
                                          nullable=False, index=True)
    # Les crédits ont-ils DÉJÀ été portés au compte ? Le webhook et la
    # consultation d'état arrivent tous les deux, souvent en double : sans ce
    # drapeau, un même paiement crédite deux fois.
    credited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone:    Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
    )


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
