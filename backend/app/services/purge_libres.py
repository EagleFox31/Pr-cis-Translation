"""Suppression des traductions en aperçu dont AUCUNE page n'a été payée.

Une traduction libre (docs/etude-traduction-libre.md) occupe le disque sans
rien rapporter tant qu'elle n'est pas débloquée. Règle (validée le 17/11) :

  * seul un document sans aucune page payée est supprimé (`paid` faux et
    `pages_libres` > 0). Un document en partie payé est GARDÉ : le client ne
    perd jamais ce qu'il a acheté ;
  * un e-mail de rappel part 5 jours avant (un seul par compte, qui liste ses
    documents) ;
  * la suppression a lieu 30 jours après la création, et jamais moins de
    5 jours après le rappel : un rappel en retard (serveur arrêté, envoi
    refusé) repousse la suppression au lieu de la rendre muette.

La date du rappel est notée dans les réglages du document (`rappel_purge`) :
pas de colonne, pas de migration. Un envoi refusé n'est pas noté, il sera
retenté le lendemain par la boucle quotidienne.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Document, User
from app.services.beta_abuse import aware
from app.services.documents import reglages_de

logger = logging.getLogger(__name__)

DELAI = timedelta(days=30)
PREAVIS = timedelta(days=5)
CLE_RAPPEL = "rappel_purge"


def _rappel_du(doc) -> datetime | None:
    brut = reglages_de(doc).get(CLE_RAPPEL)
    try:
        return aware(datetime.fromisoformat(brut)) if brut else None
    except (TypeError, ValueError):
        return None


async def _candidats(db) -> list[Document]:
    """Documents entièrement en aperçu, hors copies d'admin et travaux en cours."""
    res = await db.execute(select(Document).where(
        Document.pages_libres > 0,
        Document.paid.is_(False),
        Document.copie_de.is_(None),
        Document.status.notin_(("pending", "translating")),
    ))
    return list(res.scalars())


async def _supprimer(db, doc: Document) -> None:
    """Même effet que la suppression par le client : quota rendu, puis
    fichiers du job effacés s'ils ne servent plus à personne."""
    from app.api.documents import _racine_orpheline
    from app.services import stockage

    user = await db.get(User, doc.user_id)
    if user is not None:
        user.storage_used = max(0, (user.storage_used or 0) - (doc.storage_charged or 0))
    original_path = doc.original_path
    await db.delete(doc)
    # Commit AVANT le comptage des références : sinon la ligne se compte elle-même.
    await db.commit()
    racine = await _racine_orpheline(db, original_path)
    if racine:
        stockage.purger_racine(racine)


async def rappeler_et_purger(db, now: datetime | None = None) -> dict[str, int]:
    """Envoie les rappels dus puis supprime les documents arrivés à échéance."""
    from app.core import email as courriel

    now = now or datetime.now(timezone.utc)
    rappels: dict[str, list[Document]] = defaultdict(list)
    echus: list[Document] = []
    for doc in await _candidats(db):
        cree = aware(doc.created_at)
        rappel = _rappel_du(doc)
        if rappel is None:
            if cree <= now - DELAI + PREAVIS:
                rappels[doc.user_id].append(doc)
        elif cree <= now - DELAI and rappel <= now - PREAVIS:
            echus.append(doc)

    envoyes = 0
    for user_id, docs in rappels.items():
        user = await db.get(User, user_id)
        if user is None or not user.email:
            continue
        liste = [(d.original_name,
                  max(aware(d.created_at) + DELAI, now + PREAVIS).date().isoformat())
                 for d in docs]
        try:
            await courriel.send_rappel_libres_email(user.email, user.langue or "fr", liste)
        except courriel.EmailIndisponible:
            continue                      # retenté demain, rien n'est noté
        for d in docs:
            r = reglages_de(d)
            r[CLE_RAPPEL] = now.isoformat()
            d.reglages = json.dumps(r)
        await db.commit()
        envoyes += 1

    for doc in echus:
        await _supprimer(db, doc)
    if envoyes or echus:
        logger.info("Aperçus : %d rappel(s), %d document(s) supprimé(s)", envoyes, len(echus))
    return {"rappels": envoyes, "supprimes": len(echus)}
