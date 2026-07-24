"""Modèles de données et forfaits.

Ce module ré-exporte tout ce que le reste de l'application utilisait quand les
modèles tenaient dans un fichier unique : `from app.models import User` marche
exactement comme avant.

DEUX RAISONS de tout importer ici, et pas seulement par confort :

1. `migrations/env.py` lit `Base.metadata` pour l'autogénération. Un modèle que
   personne n'importe est un modèle absent de toutes les migrations — la table
   n'est jamais créée, et l'erreur ne surgit qu'en production.
2. SQLAlchemy résout les cibles de relation (`relationship("Document")`) par
   leur nom dans son registre. Ce registre ne connaît que les classes déjà
   importées : sans cet import groupé, l'ordre de chargement déciderait du
   succès ou de l'échec.
"""
from .base import Base, new_uuid, utcnow
from .plans import (
    FREE_PLAN,
    PLAN_LABELS,
    PLAN_MONTHLY_PAGES,
    PLAN_PAGE_LIMIT,
    PLAN_STORAGE,
    get_plan_monthly_pages,
    get_plan_page_limit,
    get_plan_storage,
    is_paid_plan,
)
from .user import User
from .document import Document
from .payment import Payment
from .auth_tokens import RefreshToken, VerificationCode

__all__ = [
    "Base", "new_uuid", "utcnow",
    "User", "Document", "Payment", "RefreshToken", "VerificationCode",
    "FREE_PLAN", "PLAN_LABELS", "PLAN_MONTHLY_PAGES", "PLAN_PAGE_LIMIT",
    "PLAN_STORAGE", "get_plan_monthly_pages", "get_plan_page_limit",
    "get_plan_storage", "is_paid_plan",
]
