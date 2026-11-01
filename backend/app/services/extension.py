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
from engines import runtags

SEGMENTS_MAX = 300
CARACTERES_MAX = 20_000
# Contexte joint (titre + blocs voisins) : le moteur n'en garde que 2 500
# caractères (`translation_ai._CONTEXTE_MAX`), on refuse au-delà de 4 fois.
CONTEXTE_MAX = 10_000
# Volume d'une page équivalente pour le texte des pages : la page de
# traduction usuelle (250 mots).
CARACTERES_PAR_PAGE = 1_500


class TraductionIndisponible(RuntimeError):
    """Le moteur n'a pas rendu de traduction : rien n'est débité."""


def pages_pour_segments(textes) -> int:
    """Volume du texte nu : les balises `[[n]]` ne se paient pas."""
    return max(1, math.ceil(sum(len(runtags.sans_balises(t)) for t in textes)
                            / CARACTERES_PAR_PAGE))


def traduire_textes(textes, langue, traducteur=None, titre="", contexte=()):
    """Une traduction par texte, dans l'ordre. Les doublons et les textes sans
    lettre (nombres, ponctuation) ne partent pas au moteur.

    Un texte est un bloc de page (§4) : ses éléments en ligne y sont des
    balises `[[n]]…[[/n]]`, que le moteur garde (il relance s'il en perd).
    Balises encore fausses au retour → le texte revient tel quel : le bloc
    reste en original plutôt que mal mis en forme.
    `titre` et `contexte` (blocs voisins, texte nu) servent le cadre de page,
    comme pour les documents ; sans contexte, le lot fait la page."""
    if traducteur is None:
        from app.services.translation_runner import ai_translator as traducteur
    if traducteur is None:
        raise TraductionIndisponible("moteur absent")
    uniques = list(dict.fromkeys(t for t in textes if any(c.isalpha() for c in t)))
    if not uniques:
        return list(textes)
    from engines.translation_ai import contexte_page
    lot = [{"id": str(i), "text": t} for i, t in enumerate(uniques)]
    page = list(contexte) or [runtags.sans_balises(t) for t in uniques]
    titres = (0,) if titre else ()
    cadre = {"n_page": len(page) + (len(uniques) if contexte else 0),
             "page": contexte_page(([titre] if titre else []) + page, titres)}
    if not traducteur._translate_batch(lot, traducteur.lang_name(langue), None,
                                       cadre=cadre):
        raise TraductionIndisponible("lot non traduit")
    rendu = {}
    for b in lot:
        sortie = b.get("translated_text") or b["text"]
        rendu[b["text"]] = b["text"] if "balises" in runtags.defauts(b["text"], sortie) else sortie
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
