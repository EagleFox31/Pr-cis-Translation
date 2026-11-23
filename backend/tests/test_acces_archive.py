"""Historique conservé, grisé sans stockage (étude Nouveautés §11).

Forfait sans stockage : accès complet 30 jours après la traduction, puis le
document est ARCHIVÉ (listé, jamais effacé, plus ouvrable : 403
`stockage_requis`). Un forfait avec stockage n'a pas de limite ; une
traduction en cours n'est jamais archivée.

Exécution :  backend/.venv/Scripts/python.exe backend/tests/test_acces_archive.py
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import racine  # noqa: F401  -- met backend/ sur le chemin

from fastapi import HTTPException                        # noqa: E402
from app.services.documents import acces_archive, acces_jusqu_au  # noqa: E402
from app.api.documents import _exiger_acces              # noqa: E402

MAINTENANT = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)


def _doc(jours: float, status: str = "done", naive: bool = False):
    cree = MAINTENANT - timedelta(days=jours)
    return SimpleNamespace(created_at=cree.replace(tzinfo=None) if naive else cree, status=status)


GRATUIT, STARTER = SimpleNamespace(plan="free"), SimpleNamespace(plan="starter")


def test_sans_stockage_accessible_avant_30_jours():
    assert not acces_archive(GRATUIT, _doc(29.9), MAINTENANT)


def test_sans_stockage_archive_apres_30_jours():
    assert acces_archive(GRATUIT, _doc(30), MAINTENANT)
    assert acces_jusqu_au(GRATUIT, _doc(30)) == MAINTENANT


def test_date_naive_lue_en_utc():
    assert acces_archive(GRATUIT, _doc(31, naive=True), MAINTENANT)


def test_forfait_avec_stockage_jamais_archive():
    assert acces_jusqu_au(STARTER, _doc(400)) is None
    assert not acces_archive(STARTER, _doc(400), MAINTENANT)


def test_traduction_en_cours_jamais_archivee():
    assert not acces_archive(GRATUIT, _doc(45, status="translating"), MAINTENANT)


def test_route_refuse_un_document_archive():
    try:
        _exiger_acces(GRATUIT, _doc(60))
        raise AssertionError("aucun refus")
    except HTTPException as e:
        assert e.status_code == 403 and e.detail == "stockage_requis"
    _exiger_acces(STARTER, _doc(60))  # ne lève pas


if __name__ == "__main__":
    tests = [f for n, f in sorted(globals().items()) if n.startswith("test_")]
    for f in tests:
        f()
        print("OK ", f.__name__)
    print(f"{len(tests)}/{len(tests)} OK")
