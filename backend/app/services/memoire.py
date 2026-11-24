"""Rendre au système la mémoire libérée par un job.

Après une traduction, CPython et les bibliothèques natives libèrent leurs
objets, mais glibc garde les pages dans ses arènes : vu du conteneur, le
processus reste au niveau de son pic et le suivant le pousse au-delà de sa
limite. `malloc_trim(0)` rend ces pages. Sans glibc (macOS, Windows, musl),
c'est un no-op.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import gc

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
