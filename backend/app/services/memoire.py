"""Mémoire disponible du conteneur, et attente quand elle manque.

Le serveur vit dans un conteneur à mémoire bornée (1 Go en production). Au-delà,
le système tue tout le processus : toutes les traductions en cours sont perdues.
Plutôt que de lancer un travail gourmand sans marge, on le fait attendre que de
la mémoire se libère.

La mesure vient du cgroup du conteneur : elle compte aussi LibreOffice et les
autres sous-processus, que la mémoire du seul processus Python ignorerait. Le
cache de fichiers n'est pas compté : le système le reprend de lui-même dès que
la mémoire manque.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import gc
import os
import threading
import time
from typing import Callable

from app.config import logger

_CGROUP = "/sys/fs/cgroup"
MO = 1024 * 1024
# Pic d'une détection d'image à pleine tuile (ocr_v2/ppocr : 1024 × 1024 points
# × 220 octets + 64 Mo de marge). Une seule détection tourne à la fois.
DETECTION_MO = 284
# Pic d'un aperçu LibreOffice (conversion Office → PDF, une seule à la fois sous
# preview_lock). Il tourne hors des places : sa mémoire est donc réservée d'office.
LIBREOFFICE_MO = 234
# Une attente ne dure jamais plus longtemps : mieux vaut tenter le travail que
# le bloquer sans fin si la mesure se trompe.
ATTENTE_MAX_S = max(1, int(os.getenv("MEMOIRE_ATTENTE_MAX_S", "600")))
_PAS_S = 0.5


def _lire(nom: str) -> str | None:
    try:
        with open(os.path.join(_CGROUP, nom), encoding="ascii") as f:
            return f.read()
    except OSError:
        return None


def disponible() -> int | None:
    """Octets encore utilisables dans le conteneur, None si inconnu (pas de
    limite, ou hors conteneur : on ne bride alors rien)."""
    limite, courant, stat = _lire("memory.max"), _lire("memory.current"), _lire("memory.stat")
    if not limite or not courant or limite.strip() == "max":
        return None
    try:
        champs = {}
        for ligne in (stat or "").splitlines():
            nom, _, val = ligne.partition(" ")
            if val.strip():
                champs[nom] = int(val)
        if "anon" in champs:     # mémoire des processus + noyau, hors cache de fichiers
            utilise = champs["anon"] + champs.get("kernel", 0) + champs.get("shmem", 0)
        else:
            utilise = int(courant) - champs.get("inactive_file", 0)
        return int(limite) - utilise
    except ValueError:
        return None


def limite() -> int | None:
    """Plafond mémoire du conteneur en octets, None s'il n'y en a pas."""
    brut = (_lire("memory.max") or "").strip()
    return int(brut) if brut.isdigit() else None


def places_pour(limite_octets: int | None, socle_mo: int, detection_mo: int,
                travail_mo: int) -> int | None:
    """Nombre de travaux qui tiennent ensemble dans le conteneur : ce qui reste
    une fois ôtés le socle du serveur au repos et les pics uniques (détection d'image
    et aperçu LibreOffice, un seul de chaque à la fois), divisé par la part d'un travail.
    Toujours au moins 1. None : pas de plafond, donc pas de budget."""
    if limite_octets is None or travail_mo <= 0:
        return None
    reste = limite_octets // MO - socle_mo - detection_mo
    return max(1, reste // travail_mo)


class Budget:
    """Places de travail communes à toutes les files (traductions et scans).
    Un travail prend une place avant de démarrer et la rend à la fin ; sans
    place libre, il attend « en file ». Le nombre de places est fixé une fois
    pour toutes : l'admission ne dépend plus d'une mesure prise au hasard d'un
    instant où les autres travaux n'ont pas encore grossi.

    Les places se donnent dans l'ORDRE D'ARRIVÉE (`attente`) : la position
    affichée à l'utilisateur est donc juste. `verrou` protège aussi l'affichage
    de la file (ordonnanceur), pour qu'aucun « en file » ne parte après le
    démarrage d'un travail."""

    def __init__(self, places: int | None):
        self.places = places
        self.verrou = threading.Condition()
        self.occupees = 0
        self.attente: list[str] = []

    def _libre(self) -> bool:
        return self.places is None or self.occupees < self.places

    def prendre_sans_attendre(self) -> bool:
        with self.verrou:
            if self.attente or not self._libre():
                return False
            self.occupees += 1
            return True

    def prendre(self, cle: str | None = None,
                sur_attente: Callable[[], None] | None = None) -> bool:
        """Prend une place, en attendant son tour si besoin. `sur_attente`
        est appelé sous le verrou dès que le travail entre en file. Rend True
        si le travail a attendu."""
        with self.verrou:
            if not self.attente and self._libre():
                self.occupees += 1
                return False
            ticket = cle if cle is not None else object()
            self.attente.append(ticket)
            if sur_attente:
                sur_attente()
            while not (self._libre() and self.attente[0] is ticket):
                self.verrou.wait()
            self.attente.pop(0)
            self.occupees += 1
            self.verrou.notify_all()
            return True

    def rendre(self) -> None:
        with self.verrou:
            self.occupees = max(0, self.occupees - 1)
            self.verrou.notify_all()


def rendre_au_systeme() -> None:
    """Rend au système la mémoire que Python a libérée mais que la bibliothèque
    C garde en réserve (sans quoi le conteneur reste plein après un gros travail)."""
    rendre_memoire()


def attendre(besoin: int, quoi: str, arret: threading.Event | None = None,
             max_s: float | None = None) -> bool:
    """Attend que `besoin` octets soient disponibles. Rend True si la marge est
    là (ou inconnue), False si l'attente a dépassé `max_s` (ATTENTE_MAX_S par
    défaut) ou si `arret` est levé : l'appelant continue quand même."""
    fin = time.monotonic() + (ATTENTE_MAX_S if max_s is None else max_s)
    signale = False
    while True:
        libre = disponible()
        if libre is None or libre >= besoin:
            if signale:
                logger.info("Mémoire : %s reprend (%d Mo libres)", quoi, libre // MO if libre else -1)
            return True
        if not signale:
            logger.warning("Mémoire : %s attend (%d Mo libres, %d Mo requis)",
                           quoi, libre // MO, besoin // MO)
            signale = True
        if time.monotonic() > fin or (arret is not None and arret.is_set()):
            logger.warning("Mémoire : %s lancé sans marge après attente", quoi)
            return False
        time.sleep(_PAS_S)

_trim = None
_cherche = False


def _fonction_trim():
    global _trim, _cherche
    if not _cherche:
        _cherche = True
        try:
            nom = ctypes.util.find_library("c")
            libc = ctypes.CDLL(nom) if nom else None
            _trim = getattr(libc, "malloc_trim", None) if libc else None
        except (OSError, AttributeError):
            _trim = None
    return _trim


def rendre_memoire() -> bool:
    """Ramasse les cycles puis rend les pages libres. Vrai si glibc a pu le
    faire ; ne lève jamais."""
    try:
        gc.collect()
        trim = _fonction_trim()
        if trim is None:
            return False
        trim(0)
        return True
    except Exception:
        return False
