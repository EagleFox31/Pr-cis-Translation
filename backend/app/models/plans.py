"""Forfaits : plafonds, quotas et droits.

Aucun modèle SQLAlchemy ici — ce sont des constantes métier et les fonctions
qui les lisent. Elles vivent à part parce que les routes, la tarification et le
lanceur de traduction en ont besoin sans rien vouloir savoir de la base.

Miroir de `frontend/src/lib/plans.ts` : toute valeur changée ici doit l'être
là-bas.
"""
from __future__ import annotations

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

PLAN_LABELS: dict[str, str] = {
    "free":       "Gratuit",
    "starter":    "Starter",
    "pro":        "Pro",
    "enterprise": "Enterprise",
    "admin":      "Admin",
}

# Le SEUL plan sans droits (ni téléchargement, ni aperçu en clair). On nomme
# l'exception plutôt que d'énumérer les plans payants : ajouter un plan ne doit
# pas obliger à penser à l'inscrire ici.
FREE_PLAN = "free"


def get_plan_page_limit(plan: str) -> int | None:
    """Pages max dans UN document pour ce plan. None = pas de plafond."""
    return PLAN_PAGE_LIMIT.get(plan, 1)  # défaut = 1 page (freemium)


def get_plan_monthly_pages(plan: str) -> int | None:
    """Pages max sur le MOIS pour ce plan. None = illimité."""
    return PLAN_MONTHLY_PAGES.get(plan, 1)


def is_paid_plan(plan: str | None) -> bool:
    """Le plan donne-t-il les droits complets ?"""
    return bool(plan) and plan != FREE_PLAN


def get_plan_storage(plan: str) -> int:
    """Limite de stockage pour un plan donné, 0 par défaut."""
    return PLAN_STORAGE.get(plan, 0)
