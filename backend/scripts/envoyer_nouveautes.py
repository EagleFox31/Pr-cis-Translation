"""Envoie l'e-mail « Nouveautés » de la version courante aux abonnés.

Toujours un essai sur sa propre adresse d'abord :

    python scripts/envoyer_nouveautes.py --depuis 2026-10-01 --essai moi@exemple.com [--langue en]

Puis l'envoi réel, étalé et repris sans doublon si on le relance :

    python scripts/envoyer_nouveautes.py --depuis 2026-10-01 [--lot 50 --pause 60]
    python scripts/envoyer_nouveautes.py --entrees id1,id2

À lancer depuis backend/.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import async_session, engine            # noqa: E402
from app.services.envoi_nouveautes import (envoyer_essai,       # noqa: E402
                                           envoyer_version)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    choix = p.add_mutually_exclusive_group(required=True)
    choix.add_argument("--entrees", help="ids du catalogue, séparés par des virgules")
    choix.add_argument("--depuis", help="éléments datés après AAAA-MM-JJ")
    p.add_argument("--essai", metavar="ADRESSE", help="un seul exemplaire, rien n'est enregistré")
    p.add_argument("--langue", default="fr", choices=("fr", "en"), help="langue de l'essai")
    p.add_argument("--lot", type=int, default=50)
    p.add_argument("--pause", type=float, default=60.0, help="secondes entre deux lots")
    a = p.parse_args()
    entrees = [x.strip() for x in a.entrees.split(",")] if a.entrees else None

    async def lancer():
        try:
            if a.essai:
                await envoyer_essai(a.essai, langue=a.langue, entrees=entrees, depuis=a.depuis)
                print(f"Essai envoyé à {a.essai} ({a.langue}).")
            else:
                await envoyer_version(async_session, entrees=entrees, depuis=a.depuis,
                                      lot=a.lot, pause=a.pause)
        finally:
            await engine.dispose()

    try:
        asyncio.run(lancer())
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
