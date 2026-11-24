"""Ménage du journal d'erreurs : il ne doit pas grossir sans fin.

Deux opérations, lancées au démarrage puis une fois par jour :

  1. `marquer_resolues` — les occurrences en attente qu'une version livrée a
     corrigées (`app/erreurs_resolues.py`) passent à `handled`. Le démarrage
     d'un conteneur EST le déploiement : c'est le bon moment pour le faire.
  2. `purger` — supprime ce qui a été traité depuis plus de
     ERROR_LOG_RETENTION_DAYS jours, et plafonne chaque groupe (même empreinte)
     à ERROR_LOG_MAX_PAR_GROUPE occurrences : une erreur en boucle garde ses
     plus récentes, le groupe reste visible, la table ne déborde pas.

Le principe du modèle tient : rien de `new` n'est supprimé pour son âge. Seul
le plafond touche des occurrences non lues, et uniquement des doublons d'un
groupe qui en garde des centaines d'autres.
"""
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update

from app.config import logger
from app.core.database import async_session
from app.models import ErrorLog, STATUS_HANDLED, STATUS_NEW

RETENTION_JOURS = max(1, int(os.getenv("ERROR_LOG_RETENTION_DAYS", "30")))
MAX_PAR_GROUPE = max(10, int(os.getenv("ERROR_LOG_MAX_PAR_GROUPE", "200")))
INTERVALLE_S = 24 * 3600


async def marquer_resolues(regles: list[dict] | None = None,
                           avant: datetime | None = None) -> int:
    """Passe à `handled` les occurrences `new` déclarées corrigées.

    `avant` borne aux occurrences créées avant cet instant (le démarrage) : une
    rechute après le déploiement reste visible.
    """
    if regles is None:
        from app.erreurs_resolues import ERREURS_RESOLUES
        regles = ERREURS_RESOLUES
    avant = avant or datetime.now(timezone.utc)
    total = 0
    async with async_session() as db:
        for regle in regles:
            motif = re.compile(regle["motif"])
            rows = (await db.execute(
                select(ErrorLog.id, ErrorLog.message).where(
                    ErrorLog.source == regle["source"],
                    ErrorLog.status == STATUS_NEW,
                    ErrorLog.created_at < avant,
                )
            )).all()
            ids = [r.id for r in rows if motif.search(r.message or "")]
            if not ids:
                continue
            await db.execute(
                update(ErrorLog).where(ErrorLog.id.in_(ids))
                .values(status=STATUS_HANDLED, handled_at=datetime.now(timezone.utc))
            )
            total += len(ids)
            logger.info("Journal : %d occurrence(s) « %s » marquée(s) résolue(s) "
                        "(corrigé en %s)", len(ids), regle["motif"],
                        regle.get("corrige_en", "?"))
        await db.commit()
    return total


async def purger(maintenant: datetime | None = None,
                 retention_jours: int = RETENTION_JOURS,
                 max_par_groupe: int = MAX_PAR_GROUPE,
                 sources: tuple[str, ...] | None = None) -> dict:
    """Supprime le traité expiré et l'excédent de chaque groupe.

    `sources` restreint la purge à ces sources (tests) ; absent, tout le journal.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    limite = maintenant - timedelta(days=retention_jours)
    portee = [ErrorLog.source.in_(sources)] if sources else []
    async with async_session() as db:
        expires = (await db.execute(
            delete(ErrorLog).where(*portee, ErrorLog.status == STATUS_HANDLED,
                                   ErrorLog.handled_at < limite)
        )).rowcount or 0

        excedent = 0
        groupes = (await db.execute(
            select(ErrorLog.fingerprint).where(*portee)
            .group_by(ErrorLog.fingerprint)
            .having(func.count() > max_par_groupe)
        )).scalars().all()
        for fp in groupes:
            anciens = (await db.execute(
                select(ErrorLog.id).where(ErrorLog.fingerprint == fp)
                .order_by(ErrorLog.created_at.desc()).offset(max_par_groupe)
            )).scalars().all()
            if anciens:
                excedent += (await db.execute(
                    delete(ErrorLog).where(ErrorLog.id.in_(anciens))
                )).rowcount or 0
        await db.commit()
    if expires or excedent:
        logger.info("Journal : %d occurrence(s) traitée(s) expirée(s), %d en "
                    "excédent de groupe, supprimées", expires, excedent)
    return {"expirees": expires, "excedent": excedent}


async def entretenir() -> None:
    """Tâche de fond du lifespan. Ne lève JAMAIS : un ménage raté ne doit ni
    empêcher de démarrer, ni arrêter la boucle."""
    demarrage = datetime.now(timezone.utc)
    try:
        await marquer_resolues(avant=demarrage)
    except Exception as exc:   # noqa: BLE001
        print(f"[error_log_menage] marquage impossible : {exc}", flush=True)
    while True:
        try:
            await purger()
        except Exception as exc:   # noqa: BLE001
            print(f"[error_log_menage] purge impossible : {exc}", flush=True)
        await asyncio.sleep(INTERVALLE_S)
