"""Qui est en quelle version, en un seul endroit.

QUATRE NIVEAUX, ET C'EST VOULU
------------------------------
    projet    -- ce qu'on livre. Le seul numéro qu'un utilisateur voit.
    backend   -- le contrat HTTP.
    frontend  -- l'interface.
    moteurs   -- un par format ; ils bougent à leur rythme.

Un correctif de rendu PPTX ne concerne ni l'API ni l'interface : lui imposer le
numéro du projet, c'est prétendre que tout a changé et rendre l'historique
illisible. À l'inverse, un seul numéro global permet de dire « la 1.2.0 » sans
énumérer cinq composants.

Chaque numéro a UNE source, et ce module ne fait que les lire :

    projet    package.json (racine)
    frontend  frontend/package.json
    backend   backend/version.py
    moteurs   backend/engines/<format>/version.py

Les deux `package.json` sont lus sur DISQUE et non recopiés ici : une constante
Python recopiée diverge, et personne ne s'en aperçoit avant la mise en
production.
"""
from __future__ import annotations

import json
from functools import lru_cache

from app.config import BACKEND_DIR, REPO_ROOT

INCONNU = "?"


@lru_cache(maxsize=8)
def _depuis_package_json(chemin: str) -> str:
    """Champ `version` d'un package.json, ou « ? » s'il est illisible.

    Illisible n'est pas fatal : une version manquante dégrade l'affichage, elle
    n'empêche pas de servir. Faire échouer le démarrage pour un numéro absent
    serait hors de proportion.
    """
    try:
        with open(chemin, encoding="utf-8") as f:
            return str(json.load(f).get("version") or INCONNU)
    except Exception:
        return INCONNU


def projet() -> str:
    return _depuis_package_json(str(REPO_ROOT / "package.json"))


def frontend() -> str:
    return _depuis_package_json(str(REPO_ROOT / "frontend" / "package.json"))


def backend() -> str:
    from version import __version__
    return __version__


def moteurs() -> dict[str, str]:
    """Version de chaque moteur, indexée par format.

    On balaie les PAQUETS (`engines/<format>/version.py`) et non le registre.
    Le registre ne connaît que les moteurs qui implémentent `TranslationEngine`
    — le moteur PDF, lui, est piloté par `engines.pdf.stream` en traduction
    progressive et n'y figure pas. Le lister depuis le registre reviendrait à
    prétendre qu'il n'existe pas, alors qu'il fait le plus gros du travail.
    """
    import importlib

    out: dict[str, str] = {}
    racine = BACKEND_DIR / "engines"
    for dossier in sorted(racine.iterdir()) if racine.is_dir() else []:
        if not (dossier / "version.py").is_file():
            continue
        try:
            mod = importlib.import_module(f"engines.{dossier.name}.version")
            out[dossier.name] = getattr(mod, "__version__", INCONNU)
        except Exception:
            out[dossier.name] = INCONNU
    return out


def toutes() -> dict:
    """Tableau complet — sert la bannière de démarrage, `/health` et la doc."""
    return {
        "projet": projet(),
        "backend": backend(),
        "frontend": frontend(),
        "moteurs": moteurs(),
    }
