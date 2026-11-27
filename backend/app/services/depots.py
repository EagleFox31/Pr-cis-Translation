"""Fichiers déposés avant la traduction (envoi unique, docs/etude-test-gros-fichier.md).

Le navigateur envoie le fichier UNE fois, dès qu'il est choisi. L'analyse,
l'aperçu de l'original et la traduction le relisent ensuite par son
identifiant au lieu de le renvoyer : un PowerPoint de 20 Mo partait jusqu'à
quatre fois, et ces envois se partageaient la connexion.

Un dépôt n'est lisible que par le compte qui l'a envoyé. Il est effacé
24 heures après son envoi, qu'il ait servi ou non.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import time

from app.config import TRANSLATIONS_DIR, logger

DOSSIER = os.path.join(TRANSLATIONS_DIR, "_depots")
CONSERVATION_S = 24 * 3600
PURGE_TOUS_S = 3600
# Envois en cours d'écriture (`_recu_*`) : jamais touchés tant qu'ils sont
# récents ; un reste d'envoi coupé est effacé au bout d'une heure.
RECU_CONSERVATION_S = 3600
PREFIXE_RECU = "_recu_"
_ID = re.compile(r"^[a-f0-9]{32}$")
_derniere_purge = 0.0


def _chemin(depot_id: str) -> str | None:
    return os.path.join(DOSSIER, depot_id) if _ID.match(depot_id or "") else None


def creer(user_id: int, nom: str, flux_vers) -> str:
    """Crée le dossier du dépôt ; `flux_vers(chemin)` y écrit le fichier.
    Retourne l'identifiant. En cas d'échec, rien ne reste sur le disque."""
    purger_parfois()
    depot_id = secrets.token_hex(16)
    dossier = os.path.join(DOSSIER, depot_id)
    os.makedirs(dossier)
    try:
        taille = flux_vers(os.path.join(dossier, "fichier"))
        with open(os.path.join(dossier, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({"user_id": user_id, "nom": nom, "taille": taille,
                       "cree": time.time()}, f, ensure_ascii=False)
    except BaseException:
        shutil.rmtree(dossier, ignore_errors=True)
        raise
    return depot_id


def lire(depot_id: str, user_id: int) -> tuple[str, bytes] | None:
    """(nom, contenu) du dépôt, ou None s'il n'existe plus, a expiré ou
    appartient à un autre compte (même réponse : on ne dit pas lequel)."""
    dossier = _chemin(depot_id)
    if not dossier:
        return None
    try:
        with open(os.path.join(dossier, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        if meta.get("user_id") != user_id or time.time() - meta.get("cree", 0) > CONSERVATION_S:
            return None
        with open(os.path.join(dossier, "fichier"), "rb") as f:
            return meta.get("nom") or "", f.read()
    except (OSError, ValueError):
        return None


def purger(maintenant: float | None = None) -> int:
    """Efface les dépôts de plus de 24 heures (et les restes d'un envoi coupé)."""
    maintenant = maintenant or time.time()
    limite = maintenant - CONSERVATION_S
    n = 0
    try:
        noms = os.listdir(DOSSIER)
    except OSError:
        return 0
    for nom in noms:
        dossier = os.path.join(DOSSIER, nom)
        if nom.startswith(PREFIXE_RECU):
            # Fichier d'un envoi : récent, il est peut-être encore en cours.
            try:
                if os.path.getmtime(dossier) < maintenant - RECU_CONSERVATION_S:
                    os.remove(dossier)
            except OSError:
                pass
            continue
        try:
            if os.path.getmtime(dossier) < limite:
                shutil.rmtree(dossier)
                n += 1
        except OSError:
            pass
    return n


def purger_parfois() -> None:
    global _derniere_purge
    if time.time() - _derniere_purge < PURGE_TOUS_S:
        return
    _derniere_purge = time.time()
    if n := purger():
        logger.info(f"Dépôts : {n} fichier(s) de plus de 24 h effacé(s).")
