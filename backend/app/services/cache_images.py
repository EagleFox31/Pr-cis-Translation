"""Cache des images traduites par l'extension (étude vitesse-images-extension).

Clé : empreinte SHA-256 des octets reçus + langue cible. Une image déjà
traduite, par n'importe quel compte, revient sans OCR ni traduction. Le cache
est partagé entre comptes mais ne se consulte pas : il faut envoyer l'image
elle-même pour la retrouver. Seules les images remplacées y entrent ; chaque
entrée est effacée 30 jours après son écriture.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time

from app.config import TRANSLATIONS_DIR, logger

DOSSIER = os.path.join(TRANSLATIONS_DIR, "_images_extension")
# Les suites de tests le coupent (tests/racine.py) : une image déjà vue
# changerait le résultat d'une suite à l'autre.
ACTIF = os.getenv("PRECIS_CACHE_IMAGES", "1") != "0"
CONSERVATION_S = 30 * 86400
PURGE_TOUS_S = 6 * 3600
# À changer quand le rendu du moteur change : les anciennes entrées ne sont plus lues.
VERSION = "1"
_LANGUE = re.compile(r"^[A-Za-z0-9_-]{1,16}$")
_derniere_purge = 0.0


def cle(data: bytes, langue: str) -> str | None:
    """None pour une langue hors format : pas de cache plutôt qu'une clé partagée."""
    if not _LANGUE.match(langue):
        return None
    return f"{hashlib.sha256(data).hexdigest()}-{langue}-v{VERSION}"


def _chemins(c: str, dossier: str) -> tuple[str, str]:
    base = os.path.join(dossier, c[:2], c)
    return base + ".json", base + ".bin"


def lire(c: str, dossier: str | None = None, maintenant: float | None = None) -> dict | None:
    """`{"mime", "blocs", "image": bytes}` ou None (absente, expirée, illisible)."""
    meta, binaire = _chemins(c, dossier or DOSSIER)
    try:
        if (maintenant or time.time()) - os.path.getmtime(meta) > CONSERVATION_S:
            return None
        with open(meta, encoding="utf-8") as f:
            entree = json.load(f)
        with open(binaire, "rb") as f:
            entree["image"] = f.read()
        return entree
    except (OSError, ValueError):
        return None


def _ecrire_atomique(chemin: str, contenu: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(chemin), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(contenu)
        os.replace(tmp, chemin)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def ecrire(c: str, mime: str, blocs: list[dict], image: bytes, dossier: str | None = None) -> None:
    """Garde l'image ; un échec d'écriture ne fait jamais échouer la requête."""
    meta, binaire = _chemins(c, dossier or DOSSIER)
    try:
        os.makedirs(os.path.dirname(meta), exist_ok=True)
        # Le binaire d'abord : une entrée lisible est toujours complète.
        _ecrire_atomique(binaire, image)
        _ecrire_atomique(meta, json.dumps({"mime": mime, "blocs": blocs},
                                          ensure_ascii=False).encode("utf-8"))
    except OSError as e:
        logger.warning(f"Cache des images : écriture impossible ({e}).")
    purger_parfois(dossier)


def purger(dossier: str | None = None, maintenant: float | None = None) -> int:
    """Efface les entrées de plus de 30 jours (et les restes d'écriture)."""
    limite = (maintenant or time.time()) - CONSERVATION_S
    n = 0
    for racine, _, fichiers in os.walk(dossier or DOSSIER):
        for nom in fichiers:
            chemin = os.path.join(racine, nom)
            try:
                if os.path.getmtime(chemin) < limite:
                    os.unlink(chemin)
                    n += nom.endswith(".json")
            except OSError:
                pass
    return n


def purger_parfois(dossier: str | None = None) -> None:
    global _derniere_purge
    if time.time() - _derniere_purge < PURGE_TOUS_S:
        return
    _derniere_purge = time.time()
    try:
        if n := purger(dossier):
            logger.info(f"Cache des images : {n} entrée(s) de plus de 30 jours effacée(s).")
    except OSError as e:
        logger.warning(f"Cache des images : purge impossible ({e}).")
