"""Bornes par page de l'extension (étude limites-page-extension).

  • une page accepte tant que son compteur est sous la borne, puis refuse sans compter ;
  • chaque page et chaque utilisateur ont leur propre budget ;
  • l'identifiant est nettoyé et tronqué ; absent → budget commun ;
  • la route rend 413 `page_limit` avec le nom de la borne.

Exécution :  backend/venv/Scripts/python.exe backend/tests/test_limites_page.py
Sans base de données.
"""
from __future__ import annotations
import sys

import racine  # noqa: F401  -- met backend/ sur le chemin

from app.api import extension as route                   # noqa: E402
from app.services import limites_page as lp              # noqa: E402


class _Req:
    def __init__(self, page):
        self.headers = {"x-page": page}


class _User:
    id = "u1"


def test_bornes():
    lp.reinitialiser()
    assert lp.prendre("u1", "p1", texte=lp.TEXTE_MAX - 1, lots=1) is None
    # Sous la borne : le dernier lot passe, même s'il la dépasse.
    assert lp.prendre("u1", "p1", texte=20_000, lots=1) is None
    assert lp.prendre("u1", "p1", texte=10, lots=1) == "texte"
    # Refus sans rien compter : les images de la page restent libres.
    assert lp._compteurs[("u1", "p1")]["lots"] == 2
    assert lp.prendre("u1", "p1", images=1) is None
    # Autre page, autre utilisateur : budgets neufs.
    assert lp.prendre("u1", "p2", texte=10, lots=1) is None
    assert lp.prendre("u2", "p1", texte=10, lots=1) is None


def test_images_et_lots():
    lp.reinitialiser()
    for _ in range(lp.IMAGES_MAX):
        assert lp.prendre("u1", "p", images=1) is None
    assert lp.prendre("u1", "p", images=1) == "images"
    assert lp.prendre("u1", "p", captures=1) is None
    for _ in range(lp.LOTS_MAX):
        assert lp.prendre("u1", "q", texte=1, lots=1) is None
    assert lp.prendre("u1", "q", texte=1, lots=1) == "lots"


def test_cle_page():
    assert lp.cle_page(None) == ""
    assert lp.cle_page("ab-12/../x y") == "ab-12xy"
    assert len(lp.cle_page("a" * 500)) == lp.ID_MAX


def test_route_413():
    lp.reinitialiser()
    lp.prendre("u1", "pp", images=lp.IMAGES_MAX)
    rep = route._limite(_Req("pp"), _User(), images=1)
    assert rep.status_code == 413 and b'"limite":"images"' in rep.body
    assert route._limite(_Req("autre"), _User(), images=1) is None
    assert route._limite(None, _User(), texte=1, lots=1) is None


if __name__ == "__main__":
    echecs = 0
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            try:
                f()
                print(f"OK   {nom}")
            except AssertionError as e:
                echecs += 1
                print(f"ÉCHEC {nom} {e}")
    sys.exit(1 if echecs else 0)
