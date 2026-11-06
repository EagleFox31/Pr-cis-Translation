"""Guichet de l'OCR : UNE lecture à la fois sur la machine, servie par priorité.

Lire une page est lourd (CPU) : deux lectures simultanées se ralentissent
mutuellement et font dépasser les délais. Le guichet n'en laisse passer qu'une.
Ceux qui attendent sont servis par priorité du plan (plus grand = d'abord),
puis par ordre d'arrivée. Garde-fou anti-famine : un ticket qui attend depuis
plus de `OCR_FILE_ANTI_FAMINE_S` passe devant tout le monde (le plus ancien
d'abord), pour qu'un compte gratuit ne reste pas bloqué derrière un flot de
comptes payants.

Usage :

    with ocr_file.tour(arret=lambda: jobs.verifier_arret(job_id)):
        ...lecture...

`arret` est appelé à chaque réveil (environ chaque seconde) pendant l'attente :
s'il lève (`ArretDemande`), le ticket est retiré proprement et l'exception
traverse. `delai` : au-delà, `OCROccupe` (ticket retiré aussi). Le tour n'est
pas réentrant : un fil qui le tient déjà et le redemande lèverait un blocage
muet, on le refuse donc tout de suite.

Ce module n'importe rien de l'application hors la configuration, pour éviter
tout import circulaire.
"""
from __future__ import annotations

import heapq
import itertools
import threading
import time
from typing import Callable

from app.config import OCR_FILE_ANTI_FAMINE_S

# Période de réveil d'un ticket en attente (arrêt demandé, délai).
_PAS_S = 1.0


class OCROccupe(Exception):
    """Le guichet est resté occupé plus longtemps que le délai accordé."""


_local = threading.local()


def definir_priorite(priorite: int) -> None:
    """Fixe la priorité par défaut des tours demandés par le fil courant."""
    _local.priorite = int(priorite)


def priorite_du_fil() -> int:
    return getattr(_local, "priorite", 0)


class Guichet:
    """Un seul exemplaire par processus (`guichet`) ; les tests en créent."""

    def __init__(self, anti_famine_s: float | None = None,
                 horloge: Callable[[], float] = time.monotonic) -> None:
        self._cond = threading.Condition()
        self._tas: list[tuple[int, int]] = []        # (-priorité, seq)
        self._arrivee: dict[int, float] = {}         # seq -> instant d'arrivée
        self._seq = itertools.count()
        self._occupe = False
        self._anti_famine_s = (OCR_FILE_ANTI_FAMINE_S if anti_famine_s is None
                               else anti_famine_s)
        self._horloge = horloge

    # ── Lecture d'état (affichage, tests) ────────────────────────────────────
    def en_attente(self) -> int:
        with self._cond:
            return len(self._arrivee)

    def occupe(self) -> bool:
        with self._cond:
            return self._occupe

    # ── Choix du prochain ticket (verrou tenu) ───────────────────────────────
    def _prochain(self) -> int | None:
        """seq du ticket à servir : le plus ancien parmi ceux qui attendent
        depuis plus que le seuil anti-famine, sinon la tête du tas."""
        if not self._arrivee:
            return None
        maintenant = self._horloge()
        affames = [(t, s) for s, t in self._arrivee.items()
                   if maintenant - t > self._anti_famine_s]
        if affames:
            return min(affames)[1]
        while self._tas and self._tas[0][1] not in self._arrivee:
            heapq.heappop(self._tas)                 # ticket déjà retiré
        return self._tas[0][1] if self._tas else None

    def _retirer(self, seq: int) -> None:
        self._arrivee.pop(seq, None)
        # Le tas est nettoyé paresseusement dans `_prochain`.

    def acquerir(self, priorite: int | None = None, delai: float | None = None,
                 arret: Callable[[], None] | None = None) -> int:
        if getattr(_local, "tient", False):
            raise RuntimeError("Tour OCR non réentrant : ce fil le tient déjà.")
        prio = priorite_du_fil() if priorite is None else int(priorite)
        debut = self._horloge()
        with self._cond:
            seq = next(self._seq)
            heapq.heappush(self._tas, (-prio, seq))
            self._arrivee[seq] = debut
            try:
                while True:
                    if not self._occupe and self._prochain() == seq:
                        self._retirer(seq)
                        self._occupe = True
                        _local.tient = True
                        return seq
                    if arret is not None:
                        arret()
                    attente = _PAS_S
                    if delai is not None:
                        reste = delai - (self._horloge() - debut)
                        if reste <= 0:
                            raise OCROccupe("Lecture occupée : réessayez.")
                        attente = min(attente, reste)
                    self._cond.wait(attente)
            except BaseException:
                self._retirer(seq)
                self._cond.notify_all()
                raise

    def liberer(self) -> None:
        with self._cond:
            self._occupe = False
            _local.tient = False
            self._cond.notify_all()

    def tour(self, priorite: int | None = None, delai: float | None = None,
             arret: Callable[[], None] | None = None) -> "_Tour":
        return _Tour(self, priorite, delai, arret)


class _Tour:
    def __init__(self, guichet: Guichet, priorite, delai, arret) -> None:
        self._g, self._p, self._d, self._a = guichet, priorite, delai, arret

    def __enter__(self) -> "_Tour":
        self._g.acquerir(self._p, self._d, self._a)
        return self

    def __exit__(self, *exc) -> None:
        self._g.liberer()


guichet = Guichet()


def tour(priorite: int | None = None, delai: float | None = None,
         arret: Callable[[], None] | None = None) -> _Tour:
    """Tour sur le guichet du processus (voir la docstring du module)."""
    return guichet.tour(priorite, delai, arret)
