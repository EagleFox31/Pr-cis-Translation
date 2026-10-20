"""Ménage du journal d'erreurs — marquage des erreurs corrigées, purge.

Ce qui est MESURÉ, jamais supposé :
  • une erreur déclarée corrigée passe à `handled` si elle date d'AVANT le
    démarrage ; la même erreur survenue après reste `new` (rechute visible) ;
  • une règle ne touche ni un autre message, ni une autre source ;
  • la purge supprime le traité expiré, garde le traité récent et ne supprime
    jamais du `new` pour son âge ;
  • un groupe au-delà du plafond garde ses occurrences les plus RÉCENTES ;
  • chaque entrée de `app/erreurs_resolues.py` est complète et son motif
    compile — la règle ResizeObserver reconnaît le message réel de la prod.

Exécution :  backend/venv/Scripts/python.exe backend/tests/test_error_log_menage.py
Requiert PostgreSQL et la migration 0006.
"""
from __future__ import annotations
import asyncio
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone

import racine  # noqa: F401  -- met backend/ sur le chemin

from sqlalchemy import delete, select                    # noqa: E402

from app.core.database import async_session, engine      # noqa: E402
from app.erreurs_resolues import ERREURS_RESOLUES        # noqa: E402
from app.models import ErrorLog, STATUS_HANDLED, STATUS_NEW  # noqa: E402
from app.services import error_log_menage as menage      # noqa: E402

# Source propre au test : la purge est bornée à elle, le journal réel n'est
# jamais touché.
SRC = f"t-{uuid.uuid4().hex[:8]}"
AUTRE = f"u-{uuid.uuid4().hex[:8]}"

_checks: list[tuple[bool, str]] = []


def check(cond: bool, label: str) -> None:
    _checks.append((bool(cond), label))
    print(f"  {'OK ' if cond else 'XX '} {label}")


def _ligne(message: str, *, source: str = SRC, fp: str = "fp", status=STATUS_NEW,
           created_at: datetime, handled_at: datetime | None = None) -> ErrorLog:
    return ErrorLog(source=source, level="error", message=message,
                    fingerprint=f"{SRC}-{fp}", status=status,
                    created_at=created_at, handled_at=handled_at)


async def _statut(db, message: str, source: str = SRC) -> str | None:
    return (await db.execute(select(ErrorLog.status).where(
        ErrorLog.source == source, ErrorLog.message == message))).scalar()


async def main() -> None:
    now = datetime.now(timezone.utc)
    demarrage = now - timedelta(minutes=1)

    # ── 1. Marquage des erreurs corrigées ─────────────────────────────────────
    async with async_session() as db:
        db.add_all([
            _ligne("Boom corrigé (avant)", created_at=now - timedelta(days=2)),
            _ligne("Boom corrigé (après)", created_at=now),
            _ligne("Autre panne", created_at=now - timedelta(days=2)),
            _ligne("Boom corrigé (avant)", source=AUTRE, created_at=now - timedelta(days=2)),
        ])
        await db.commit()
    regles = [{"source": SRC, "motif": r"^Boom corrigé", "corrige_en": "9.9.9"}]
    n = await menage.marquer_resolues(regles, avant=demarrage)
    async with async_session() as db:
        check(await _statut(db, "Boom corrigé (avant)") == STATUS_HANDLED,
              "occurrence antérieure au démarrage marquée traitée")
        check(await _statut(db, "Boom corrigé (après)") == STATUS_NEW,
              "occurrence postérieure (rechute) laissée en new")
        check(await _statut(db, "Autre panne") == STATUS_NEW,
              "message non visé laissé en new")
        check(await _statut(db, "Boom corrigé (avant)", AUTRE) == STATUS_NEW,
              "autre source laissée en new")
        h = (await db.execute(select(ErrorLog.handled_at).where(
            ErrorLog.source == SRC, ErrorLog.message == "Boom corrigé (avant)"))).scalar()
        check(h is not None, "handled_at renseigné")
    check(n == 1, f"une seule occurrence marquée (obtenu {n})")
    check(await menage.marquer_resolues(regles, avant=demarrage) == 0,
          "relancé, le marquage ne retouche rien")

    # ── 2. Purge du traité expiré ─────────────────────────────────────────────
    async with async_session() as db:
        await db.execute(delete(ErrorLog).where(ErrorLog.source.in_([SRC, AUTRE])))
        db.add_all([
            _ligne("traité vieux", fp="a", status=STATUS_HANDLED,
                   created_at=now - timedelta(days=60), handled_at=now - timedelta(days=40)),
            _ligne("traité récent", fp="b", status=STATUS_HANDLED,
                   created_at=now - timedelta(days=60), handled_at=now - timedelta(days=5)),
            _ligne("new vieux", fp="c", created_at=now - timedelta(days=90)),
        ])
        await db.commit()
    res = await menage.purger(retention_jours=30, max_par_groupe=10, sources=(SRC,))
    async with async_session() as db:
        check(await _statut(db, "traité vieux") is None, "traité depuis 40 j supprimé")
        check(await _statut(db, "traité récent") == STATUS_HANDLED, "traité depuis 5 j gardé")
        check(await _statut(db, "new vieux") == STATUS_NEW, "new de 90 j jamais supprimé")
    check(res == {"expirees": 1, "excedent": 0}, f"bilan de purge exact ({res})")

    # ── 3. Plafond par groupe ─────────────────────────────────────────────────
    async with async_session() as db:
        db.add_all([_ligne(f"boucle {i:02d}", fp="boucle",
                           created_at=now - timedelta(minutes=i)) for i in range(15)])
        await db.commit()
    res = await menage.purger(retention_jours=30, max_par_groupe=10, sources=(SRC,))
    async with async_session() as db:
        restes = (await db.execute(select(ErrorLog.message).where(
            ErrorLog.fingerprint == f"{SRC}-boucle"))).scalars().all()
    check(len(restes) == 10, f"groupe ramené à 10 occurrences ({len(restes)})")
    check(sorted(restes) == [f"boucle {i:02d}" for i in range(10)],
          "les 10 plus récentes sont celles gardées")
    check(res["excedent"] == 5, f"5 occurrences en excédent supprimées ({res})")

    # ── 4. Registre des erreurs corrigées ─────────────────────────────────────
    complet = all({"source", "motif", "corrige_en", "note"} <= set(r) for r in ERREURS_RESOLUES)
    check(complet, "chaque entrée du registre est complète")
    try:
        motifs = [re.compile(r["motif"]) for r in ERREURS_RESOLUES]
        check(True, "chaque motif du registre compile")
    except re.error as exc:
        motifs = []
        check(False, f"motif invalide : {exc}")
    prod = "ResizeObserver loop completed with undelivered notifications."
    check(any(m.search(prod) for m in motifs), "la règle ResizeObserver reconnaît le message prod")

    await _purger()

    passed = sum(1 for ok, _ in _checks if ok)
    total = len(_checks)
    print(f"\n{passed}/{total} contrôles")
    if passed != total:
        print("ÉCHECS :", [lbl for ok, lbl in _checks if not ok])
        sys.exit(1)
    print("OK — ménage du journal conforme")


async def _purger() -> None:
    async with async_session() as db:
        await db.execute(delete(ErrorLog).where(ErrorLog.source.in_([SRC, AUTRE])))
        await db.commit()
    await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SystemExit:
        raise
    except BaseException:
        asyncio.run(_purger())
        raise
