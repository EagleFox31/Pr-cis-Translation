"""File des conversions LibreOffice : bornée, avec priorité.

LibreOffice ne convertit qu'un document à la fois (profil partagé, voir
`engines.office.preview_lock`). Sans file, vingt envois dans la même minute
mettent vingt conversions « préparées à l'avance » devant l'aperçu d'un
utilisateur qui traduit.

Deux priorités :
- URGENTE : un écran attend le résultat (aperçu d'une traduction en cours,
  aperçu à la demande). Elle passe avant toute conversion à l'avance, et ne
  se refuse jamais ;
- À L'AVANCE : préparée pendant que l'utilisateur choisit sa langue. Elle est
  abandonnée si son fichier a été remplacé ou supprimé avant son tour, et
  ignorée si la file est déjà pleine (`maximum`) : elle se refera à la demande.

À priorité égale, l'ordre d'arrivée est respecté.
"""
from __future__ import annotations

import asyncio
import contextlib
import threading
from typing import Callable

from app.config import LIBREOFFICE_FILE_MAX

# Un demandeur en attente vérifie son abandon à cette cadence : une conversion
# devenue inutile libère sa place sans attendre son tour.
_VEILLE_S = 0.5
# Cadence à laquelle une attente asynchrone revérifie son tour (sans thread).
_VEILLE_ASYNC_S = 0.05


class ConversionAbandonnee(Exception):
    """Conversion à l'avance non faite (file pleine, ou fichier remplacé) : ce
    n'est pas une erreur, elle se refera à la demande."""


class _Demande:
    __slots__ = ("priorite", "numero", "abandon")

    def __init__(self, priorite: int, numero: int, abandon):
        self.priorite, self.numero, self.abandon = priorite, numero, abandon


class FileConversions:
    URGENTE, A_L_AVANCE = 0, 1

    def __init__(self, maximum: int | None, simultanees: int = 1):
        self.maximum = maximum
        self.simultanees = simultanees
        self._cond = threading.Condition()
        self._en_cours = 0
        self._attente: list[_Demande] = []
        self._numero = 0

    @property
    def en_attente(self) -> int:
        return len(self._attente)

    def _tete(self) -> _Demande:
        return min(self._attente, key=lambda d: (d.priorite, d.numero))

    def _inscrire(self, a_l_avance: bool, abandon) -> _Demande:
        """Entre dans la file (verrou `_cond` tenu) ; refuse une conversion à
        l'avance quand la file est pleine."""
        if a_l_avance and self.maximum and len(self._attente) >= self.maximum:
            raise ConversionAbandonnee("file LibreOffice pleine")
        self._numero += 1
        demande = _Demande(self.A_L_AVANCE if a_l_avance else self.URGENTE,
                           self._numero, abandon if a_l_avance else None)
        self._attente.append(demande)
        return demande

    @contextlib.contextmanager
    def tour(self, a_l_avance: bool = False,
             abandon: Callable[[], bool] | None = None):
        """Attend son tour de conversion. Lève `ConversionAbandonnee` pour une
        conversion à l'avance ignorée ou devenue inutile ; ne lève jamais pour
        une conversion urgente. Bloque le THREAD appelant : le code asynchrone
        prend `tour_async`."""
        with self._cond:
            demande = self._inscrire(a_l_avance, abandon)
            try:
                while True:
                    if demande.abandon is not None and demande.abandon():
                        raise ConversionAbandonnee("fichier remplacé ou supprimé")
                    if self._en_cours < self.simultanees and self._tete() is demande:
                        break
                    self._cond.wait(_VEILLE_S if demande.abandon else None)
            except BaseException:
                self._attente.remove(demande)
                self._cond.notify_all()
                raise
            self._attente.remove(demande)
            self._en_cours += 1
        try:
            yield
        finally:
            with self._cond:
                self._en_cours -= 1
                self._cond.notify_all()

    @contextlib.asynccontextmanager
    async def tour_async(self, a_l_avance: bool = False,
                         abandon: Callable[[], bool] | None = None):
        """Comme `tour`, sans occuper de thread : seule la coroutine attend.
        Même file, mêmes priorités, même plafond que `tour`. Une coroutine
        annulée quitte la file proprement (sa place ne bloque personne)."""
        with self._cond:
            demande = self._inscrire(a_l_avance, abandon)
        try:
            while True:
                with self._cond:
                    if demande.abandon is not None and demande.abandon():
                        raise ConversionAbandonnee("fichier remplacé ou supprimé")
                    if self._en_cours < self.simultanees and self._tete() is demande:
                        self._attente.remove(demande)
                        self._en_cours += 1
                        break
                await asyncio.sleep(_VEILLE_ASYNC_S)
        except BaseException:
            with self._cond:
                if demande in self._attente:
                    self._attente.remove(demande)
                self._cond.notify_all()
            raise
        try:
            yield
        finally:
            with self._cond:
                self._en_cours -= 1
                self._cond.notify_all()


file_conversions = FileConversions(LIBREOFFICE_FILE_MAX)
