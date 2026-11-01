"""Traduction pour l'extension navigateur (étude extension §6 et §8).

Deux services, sans rien conserver (ni texte de page, ni image) :
- `traduire_textes` : segments d'une page, par le moteur des documents ;
- `couverture` / `debiter` : la règle de débit des documents, appliquée à une
  image remplacée (1 page équivalente) ou à un lot de segments (au volume).
"""
from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (User, get_plan_monthly_pages,
                        KIND_CREDITS, KIND_FREE_OFFER, KIND_PLAN)
from app.services import usage

SEGMENTS_MAX = 300
CARACTERES_MAX = 20_000
# Volume d'une page équivalente pour le texte « qualité Précis » : la page
# de traduction usuelle (250 mots).
CARACTERES_PAR_PAGE = 1_500


class TraductionIndisponible(RuntimeError):
    """Le moteur n'a pas rendu de traduction : rien n'est débité."""


def pages_pour_segments(textes) -> int:
    return max(1, math.ceil(sum(len(t) for t in textes) / CARACTERES_PAR_PAGE))


def traduire_textes(textes, langue, traducteur=None):
    """Une traduction par texte, dans l'ordre. Les doublons et les textes sans
    lettre (nombres, ponctuation) ne partent pas au moteur."""
    if traducteur is None:
        from app.services.translation_runner import ai_translator as traducteur
    if traducteur is None:
        raise TraductionIndisponible("moteur absent")
    uniques = list(dict.fromkeys(t for t in textes if any(c.isalpha() for c in t)))
    if not uniques:
        return list(textes)
    lot = [{"id": str(i), "text": t} for i, t in enumerate(uniques)]
    if not traducteur._translate_batch(lot, traducteur.lang_name(langue), None):
        raise TraductionIndisponible("lot non traduit")
    rendu = {b["text"]: b.get("translated_text") or b["text"] for b in lot}
    return [rendu.get(t, t) for t in textes]


async def couverture(db: AsyncSession, user: User) -> tuple[int | None, int, bool]:
    """(reste du forfait ou None si illimité, solde acheté, forfait gratuit)."""
    solde = max(0, user.page_credits)
    gratuit = user.plan == "free"
    if gratuit:
        return await usage.free_pages_remaining(db, user), solde, True
    monthly = get_plan_monthly_pages(user.plan)
    if monthly is None:
        return None, solde, False
    return max(0, monthly - await usage.pages_used_this_month(db, user)), solde, False


def couvre(reste_plan, solde, pages) -> bool:
    return reste_plan is None or reste_plan + solde >= pages


async def debiter(db: AsyncSession, user_id: str, pages: int) -> bool:
    """Débite `pages` sous verrou (forfait d'abord, puis solde acheté) et
    commite. Faux si le solde verrouillé ne couvre plus : rien n'est débité."""
    locked = (await db.execute(
        select(User).where(User.id == user_id).with_for_update()
        .execution_options(populate_existing=True)
    )).scalar_one()
    reste_plan, solde, gratuit = await couverture(db, locked)
    if not couvre(reste_plan, solde, pages):
        await db.rollback()
        return False
    du_plan = pages if reste_plan is None else min(pages, reste_plan)
    achetees = pages - du_plan
    locked.page_credits -= achetees
    if du_plan:
        usage.record(db, locked.id, None, KIND_FREE_OFFER if gratuit else KIND_PLAN, du_plan)
    if achetees:
        usage.record(db, locked.id, None, KIND_CREDITS, achetees)
    await db.commit()
    return True
