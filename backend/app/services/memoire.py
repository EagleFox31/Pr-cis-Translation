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

import asyncio
import contextlib
import ctypes
import ctypes.util
import gc
import os
import threading
import time
from typing import Callable

from app.config import COMPARTIMENT_RASTER_MAX, COMPARTIMENT_RENDUS_MAX, logger

_CGROUP = "/sys/fs/cgroup"
MO = 1024 * 1024
# Pic d'une détection d'image à pleine tuile (ocr_v2/ppocr : 1024 × 1024 points
# × 220 octets + 64 Mo de marge). Une seule détection tourne à la fois.
DETECTION_MO = 284
# Pic d'un aperçu LibreOffice (conversion Office → PDF, une seule à la fois sous
# preview_lock). Il tourne hors des places : sa mémoire est donc réservée d'office.
LIBREOFFICE_MO = 234
# Pic estimé d'un travail des compartiments (voir `Compartiment`) : reconstruire
# un document traduit prend ~3 fois sa taille ; rastériser une page, bien moins.
RENDU_MO = 200
RASTER_MO = 100
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


_reserve = 0
_reserve_verrou = threading.Lock()


def reserver(octets: int) -> None:
    """Retient une estimation de mémoire pour un travail qui démarre : sa
    consommation réelle n'apparaît dans la mesure qu'au fil du travail."""
    global _reserve
    with _reserve_verrou:
        _reserve += octets


def liberer(octets: int) -> None:
    global _reserve
    with _reserve_verrou:
        _reserve = max(0, _reserve - octets)


def reserve() -> int:
    return _reserve


def disponible() -> int | None:
    """Octets encore utilisables dans le conteneur (estimations réservées par
    les compartiments déduites), None si inconnu (pas de limite, ou hors
    conteneur : on ne bride alors rien)."""
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
        return int(limite) - utilise - _reserve
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
             max_s: float | None = None, jusqu_a_marge: bool = False) -> bool:
    """Attend que `besoin` octets soient disponibles. Rend True si la marge est
    là (ou inconnue), False si l'attente a dépassé `max_s` (ATTENTE_MAX_S par
    défaut) ou si `arret` est levé : l'appelant continue quand même.

    `jusqu_a_marge` : le travail ne démarre jamais sans marge. Passé le délai,
    l'attente est signalée au journal puis continue ; seul `arret` y met fin."""
    fin = time.monotonic() + (ATTENTE_MAX_S if max_s is None else max_s)
    signale = depasse = False
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
        if arret is not None and arret.is_set():
            logger.warning("Mémoire : %s lancé sans marge après attente", quoi)
            return False
        if time.monotonic() > fin:
            if not jusqu_a_marge:
                logger.warning("Mémoire : %s lancé sans marge après attente", quoi)
                return False
            if not depasse:
                depasse = True
                logger.warning("Mémoire : %s attend toujours ; il ne démarre pas sans marge", quoi)
        time.sleep(_PAS_S)


# ── Compartiments : travaux lourds hors traduction ───────────────────────────
#
# Reconstruire un document traduit (téléchargement, aperçu, rendu de fond) ou
# filigraner des pages ne passe pas par le Budget des traductions. Sans plafond,
# trois téléchargements simultanés d'un gros PDF, plus une traduction, dépassent
# la mémoire du conteneur. Chaque famille de travaux a donc son compartiment :
# un nombre fixe de places, prises AVANT d'entrer dans un thread (une attente
# n'en occupe aucun), et une estimation de mémoire retenue le temps du travail
# (`reserver`), que `disponible()` déduit pour les traductions qui attendent.

class _Attente:
    __slots__ = ("fond", "evenement", "boucle", "futur", "accordee")

    def __init__(self, fond: bool, boucle):
        self.fond = fond
        self.boucle = boucle
        self.accordee = False
        self.evenement = threading.Event() if boucle is None else None
        self.futur = boucle.create_future() if boucle is not None else None

    def reveiller(self) -> bool:
        """Donne la place à ce demandeur. Faux s'il a disparu (boucle fermée)."""
        self.accordee = True
        if self.boucle is None:
            self.evenement.set()
            return True
        try:
            self.boucle.call_soon_threadsafe(self._poser)
            return True
        except RuntimeError:
            self.accordee = False
            return False

    def _poser(self) -> None:
        if not self.futur.done():
            self.futur.set_result(None)


class Compartiment:
    """Un nombre fixe de places pour une famille de travaux lourds.

    Les places se donnent dans l'ordre d'arrivée. Les travaux « de fond »
    (rendus lancés sans qu'un écran les attende) ne passent qu'après tous les
    demandeurs interactifs, et le plus RÉCENT d'entre eux d'abord : ce que
    l'utilisateur vient de rouvrir compte plus que ce qu'il a survolé avant.
    `places` None : aucune limite (la mémoire reste réservée)."""

    def __init__(self, nom: str, places: int | None, mo: int):
        self.nom, self.places, self.mo = nom, places, mo
        self._verrou = threading.Lock()
        self._occupees = 0
        self._attente: list[_Attente] = []

    @property
    def occupees(self) -> int:
        return self._occupees

    @property
    def en_attente(self) -> int:
        return len(self._attente)

    def _entrer(self, fond: bool, boucle=None) -> _Attente | None:
        with self._verrou:
            if self.places is None or (self._occupees < self.places and not self._attente):
                self._occupees += 1
                return None
            attente = _Attente(fond, boucle)
            self._attente.append(attente)
            return attente

    def _choisir(self) -> _Attente:
        for a in self._attente:
            if not a.fond:
                return a
        return self._attente[-1]

    def _rendre_place(self) -> None:
        with self._verrou:
            while self._attente:
                a = self._choisir()
                self._attente.remove(a)
                if a.reveiller():
                    return              # la place passe telle quelle au suivant
            self._occupees = max(0, self._occupees - 1)

    def prendre(self, fond: bool = False) -> None:
        """Prend une place, en bloquant le THREAD appelant (code synchrone)."""
        attente = self._entrer(fond)
        if attente is not None:
            attente.evenement.wait()

    async def prendre_async(self, fond: bool = False) -> None:
        """Prend une place SANS occuper de thread : seule la coroutine attend."""
        attente = self._entrer(fond, asyncio.get_running_loop())
        if attente is None:
            return
        try:
            await attente.futur
        except BaseException:
            with self._verrou:
                if attente in self._attente:
                    self._attente.remove(attente)
                donnee = attente.accordee
            if donnee:
                self._rendre_place()    # annulée après avoir reçu la place
            raise

    @contextlib.contextmanager
    def place(self, fond: bool = False):
        self.prendre(fond)
        reserver(self.mo * MO)
        try:
            yield
        finally:
            liberer(self.mo * MO)
            self._rendre_place()

    @contextlib.asynccontextmanager
    async def place_async(self, fond: bool = False):
        await self.prendre_async(fond)
        reserver(self.mo * MO)
        try:
            yield
        finally:
            liberer(self.mo * MO)
            self._rendre_place()


rendus = Compartiment("rendus", COMPARTIMENT_RENDUS_MAX, RENDU_MO)
rasterisation = Compartiment("rasterisation", COMPARTIMENT_RASTER_MAX, RASTER_MO)


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
