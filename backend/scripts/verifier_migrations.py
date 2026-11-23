"""Garde-fou des migrations : une seule suite, et une base que ce code connaît.

Deux branches qui ajoutent chacune une migration après la même parente créent
deux « fins » de suite. Une fois fusionnées, `alembic upgrade head` refuse de
choisir et le conteneur de production ne redémarre plus. Ce script le détecte
avant : en CI (le code fusionné doit avoir une seule fin) et au lancement local.

    python scripts/verifier_migrations.py           # suite unique (CI)
    python scripts/verifier_migrations.py --base    # + base à jour (dev.py)

Code de sortie 1 si un problème est trouvé, avec la marche à suivre.
"""
from __future__ import annotations

import os
import subprocess
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _scripts() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(os.path.join(BACKEND, "alembic.ini")))


def verifier_suite() -> list[str]:
    """Problèmes de la suite de migrations du code (vide si elle est saine)."""
    tetes = _scripts().get_heads()
    if len(tetes) <= 1:
        return []
    return [
        f"Plusieurs fins de suite de migrations : {', '.join(sorted(tetes))}.",
        "Deux branches ont ajouté une migration après la même parente. Garder "
        "l'ordre de fusion : dans la migration arrivée en dernier, faire pointer "
        "`down_revision` sur la fin de l'autre suite (et renuméroter le fichier).",
    ]


def _alembic(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND,
                          capture_output=True, text=True)


def verifier_base() -> list[str]:
    """Met la base à jour ; problème si elle porte une migration inconnue ici."""
    courant = _alembic("current")
    sortie = courant.stdout + courant.stderr
    if "Can't locate revision" in sortie:
        inconnue = sortie.split("identified by", 1)[-1].strip().splitlines()[0]
        return [
            f"La base est à la migration {inconnue}, inconnue de cette branche : "
            "elle a été mise à jour depuis une autre branche.",
            "Les colonnes propres à cette branche y manquent (erreur « Erreur "
            "interne » à la connexion). Utiliser une base par branche, ou fusionner "
            "les deux suites (voir verifier_suite) avant de passer de l'une à l'autre.",
        ]
    if courant.returncode != 0:
        return [f"Base injoignable : {sortie.strip().splitlines()[-1] if sortie.strip() else '?'}"]
    maj = _alembic("upgrade", "head")
    if maj.returncode != 0:
        dernier = (maj.stdout + maj.stderr).strip().splitlines()
        return [f"Mise à jour de la base impossible : {dernier[-1] if dernier else '?'}"]
    return []


def main() -> int:
    problemes = verifier_suite()
    if not problemes and "--base" in sys.argv[1:]:
        problemes = verifier_base()
    for ligne in problemes:
        print(f"[migrations] {ligne}", file=sys.stderr)
    return 1 if problemes else 0


if __name__ == "__main__":
    sys.exit(main())
