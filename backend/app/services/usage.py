"""Consommation du mois : ce que les quotas comptent, et ce qu'il en reste.

UNE SEULE SOURCE pour la route de traduction (qui refuse) et pour le profil
(qui affiche le reste). Deux calculs séparés finiraient par diverger, et
l'interface annoncerait une traduction que la route refuse.

Tout se lit dans `usage_records`, jamais dans `documents` : un document se
supprime, une consommation non (cf. `app.models.usage`).
"""
from __future__ import annotations

import calendar
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (KIND_CREDITS, KIND_FREE_OFFER, KIND_LEGACY, UsageRecord,
                        User, get_plan_monthly_pages)


def month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def add_months(d: datetime, months: int) -> datetime:
    """Même jour, `months` mois plus tard (31 janv. + 1 mois = 28/29 févr.)."""
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return d.replace(year=year, month=month,
                     day=min(d.day, calendar.monthrange(year, month)[1]))


def quota_period(user: User, now: datetime | None = None) -> tuple[datetime, datetime]:
    """Fenêtre du quota de pages en cours : [début, fin).

    Abonnement acheté : de date à date depuis la souscription (souscrit le 28,
    le quota repart chaque 28). Au mois civil, un achat du 28 donnerait deux
    quotas en quatre jours. Sans souscription (gratuit, plan attribué par
    l'administration) : le mois civil. Chaque borne se calcule depuis le
    début, jamais de proche en proche : le 31 ne dérive pas vers le 28."""
    now = now or datetime.now(timezone.utc)
    start = user.plan_started_at
    if start is None or user.plan_expires_at is None:
        debut = month_start(now)
        return debut, add_months(debut, 1)
    # `start + k` tombe dans le mois de `now` : au plus un pas en arrière.
    k = max(0, (now.year - start.year) * 12 + now.month - start.month)
    if k > 0 and add_months(start, k) > now:
        k -= 1
    return add_months(start, k), add_months(start, k + 1)


def _du_mois(user_id: str):
    return (UsageRecord.user_id == user_id,
            UsageRecord.created_at >= month_start(),
            UsageRecord.refunded.is_(False))


async def free_pages_used(db: AsyncSession, user_id: str) -> int:
    """Pages offertes réservées ce mois-ci, même si le document a été supprimé.

    Les anciennes offres et reprises restent comptées à leur valeur réelle.
    Un remboursement est exclu ; un achat ne consomme pas ce quota.
    """
    r = await db.execute(
        select(func.coalesce(func.sum(UsageRecord.pages), 0)).where(
            *_du_mois(user_id),
            UsageRecord.kind.in_((KIND_FREE_OFFER, KIND_LEGACY)),
        )
    )
    return int(r.scalar() or 0)


async def free_offer_used(db: AsyncSession, user_id: str) -> bool:
    """Compatibilité : le quota offert du mois est-il épuisé ?"""
    return await free_pages_used(db, user_id) >= get_plan_monthly_pages("free")


async def free_pages_remaining(db: AsyncSession, user: User) -> int:
    if not user.email_verified:
        return 0
    return max(0, get_plan_monthly_pages("free") - await free_pages_used(db, user.id))


async def pages_used_this_month(db: AsyncSession, user: User) -> int:
    """Pages consommées dans la période de quota en cours (`quota_period`).

    Les pages ACHETÉES à l'unité ne sont pas du quota : elles sont payées."""
    debut, _fin = quota_period(user)
    r = await db.execute(
        select(func.coalesce(func.sum(UsageRecord.pages), 0)).where(
            UsageRecord.user_id == user.id,
            UsageRecord.created_at >= debut,
            UsageRecord.refunded.is_(False),
            UsageRecord.kind != KIND_CREDITS,
        )
    )
    return int(r.scalar() or 0)


def record(db: AsyncSession, user_id: str, document_id: str | None,
           kind: str, pages: int) -> UsageRecord:
    """Ajoute une consommation à la session — commitée avec le Document, dans
    la MÊME transaction : l'une sans l'autre serait soit un quota qui ne
    compte pas, soit une consommation fantôme."""
    rec = UsageRecord(user_id=user_id, document_id=document_id,
                      kind=kind, pages=max(1, int(pages)))
    db.add(rec)
    return rec


async def refund_for_document(db: AsyncSession, document_id: str) -> None:
    """Neutralise la consommation d'une traduction ÉCHOUÉE.

    Idempotent : un échec reporté deux fois ne rembourse qu'une fois. Les
    pages achetées reviennent au solde ; l'offre du mois redevient libre."""
    from app.services import beta
    await beta.refund_for_document(db, document_id)
    rows = (await db.execute(
        select(UsageRecord).where(UsageRecord.document_id == document_id,
                                  UsageRecord.refunded.is_(False))
        .with_for_update()
    )).scalars().all()
    for rec in rows:
        rec.refunded = True
        if rec.kind == KIND_CREDITS:
            user = await db.get(User, rec.user_id, with_for_update=True)
            if user is not None:
                user.page_credits += rec.pages


async def refund_unfinished(db: AsyncSession, document_id: str, gardees: int) -> None:
    """Rend les pages NON traduites d'un job coupé, garde `gardees` débitées.

    Arrêt du serveur, pause ou annulation : les pages livrées restent dues, le reste revient —
    d'abord les pages ACHETÉES (le titre le plus cher pour le client), puis
    le quota. Une ligne réduite à zéro passe `refunded` ; les autres gardent
    leur nombre de pages réduit. Limite : `rebill_for_document` ne rétablit
    que les lignes remboursées en entier, pas une ligne réduite ; et l'ordre
    des verrous (Document puis compte, depuis `sync_status`) est l'inverse de
    celui d'une reprise : interblocage possible, mais seulement avec deux
    processus simultanés (déploiement à un seul processus)."""
    from app.services import beta
    await beta.refund_unfinished(db, document_id, gardees)
    rows = (await db.execute(
        select(UsageRecord).where(UsageRecord.document_id == document_id,
                                  UsageRecord.refunded.is_(False))
        .with_for_update()
    )).scalars().all()
    a_rendre = max(0, sum(r.pages for r in rows) - max(0, gardees))
    for rec in sorted(rows, key=lambda r: r.kind != KIND_CREDITS):
        if a_rendre <= 0:
            break
        n = min(rec.pages, a_rendre)
        a_rendre -= n
        if n == rec.pages:
            rec.refunded = True
        else:
            rec.pages -= n
        if rec.kind == KIND_CREDITS:
            user = await db.get(User, rec.user_id, with_for_update=True)
            if user is not None:
                user.page_credits += n


async def pages_payees(db: AsyncSession, document_id: str) -> int:
    """Pages encore débitées pour ce document (titres confondus, bêta incluse)."""
    from app.services import beta
    n = (await db.execute(
        select(func.coalesce(func.sum(UsageRecord.pages), 0))
        .where(UsageRecord.document_id == document_id,
               UsageRecord.refunded.is_(False)))).scalar()
    return int(n or 0) + await beta.units_billed(db, document_id)


async def rebill_for_document(db: AsyncSession, document_id: str) -> None:
    """Annule le remboursement d'une traduction finalement LIVRÉE.

    Seul cas connu : un second processus démarre pendant qu'un premier
    traduit, et `reconcilier_jobs_orphelins` rembourse un job bien vivant,
    qui aboutit ensuite. Sans ceci, le client aurait la traduction ET ses
    pages. Un Document ne se relance jamais sous le même id : un
    enregistrement remboursé puis livré ne peut venir que de là. Le solde
    peut passer sous zéro si les pages rendues ont déjà servi : c'est la
    dette réelle, et elle bloque le prochain débit."""
    from app.services import beta
    await beta.refund_for_document(db, document_id, refunded=False)
    rows = (await db.execute(
        select(UsageRecord).where(UsageRecord.document_id == document_id,
                                  UsageRecord.refunded.is_(True))
        .with_for_update()
    )).scalars().all()
    for rec in rows:
        rec.refunded = False
        if rec.kind == KIND_CREDITS:
            user = await db.get(User, rec.user_id, with_for_update=True)
            if user is not None:
                user.page_credits -= rec.pages


async def usage_summary(db: AsyncSession, user: User) -> dict:
    """Ce qu'il reste à l'utilisateur ce mois-ci, tel que la route l'appliquera."""
    plan = user.plan
    if plan == "free":
        utilise = await free_pages_used(db, user.id)
        offert = (max(0, get_plan_monthly_pages("free") - utilise)
                  if user.email_verified else 0)
        return {
            "kind": "free",
            "monthly_pages": get_plan_monthly_pages("free"),
            "pages_used": utilise,
            "pages_remaining": offert,
            # Ancien champ conservé pour les clients déjà ouverts.
            "free_translations_remaining": offert,
            "page_credits": user.page_credits,
            "resets_at": _mois_suivant().isoformat(),
        }
    quota = get_plan_monthly_pages(plan)
    utilise = await pages_used_this_month(db, user)
    return {
        "kind": "plan",
        "monthly_pages": quota,
        "pages_used": utilise,
        "pages_remaining": None if quota is None else max(0, quota - utilise),
        "page_credits": user.page_credits,
        "resets_at": quota_period(user)[1].isoformat(),
    }


def _mois_suivant() -> datetime:
    debut = month_start()
    if debut.month == 12:
        return debut.replace(year=debut.year + 1, month=1)
    return debut.replace(month=debut.month + 1)
