"""Bornes par page de l'extension (étude limites-page-extension).

Le nombre de pages est libre ; chaque page a un budget généreux sur ce qui fait
grossir l'usage du moteur : texte envoyé, nombre de lots, images. La page est un
identifiant opaque tiré par l'extension (en-tête `X-Page`), jamais l'adresse.
Compteurs en mémoire (un seul worker), rien n'est gardé en base.
"""
from __future__ import annotations

import time

# Texte envoyé, balises comprises : environ 33 pages équivalentes.
TEXTE_MAX = 50_000
# Lots de texte : chacun renvoie le prompt et le contexte (défilement infini).
LOTS_MAX = 100
# Images traduites (texte trouvé et remplacé), le poste le plus coûteux.
IMAGES_MAX = 10
# Images analysées, avec ou sans texte : l'OCR seul, borné plus largement pour
# qu'une page riche en illustrations ne bloque pas ses vraies images à texte.
ANALYSES_MAX = 60
# Images de vidéo, prises à la demande sur pause.
CAPTURES_MAX = 20

BORNES = {"texte": TEXTE_MAX, "lots": LOTS_MAX, "images": IMAGES_MAX,
          "analyses": ANALYSES_MAX, "captures": CAPTURES_MAX}

DUREE_S = 6 * 3600
PAGES_SUIVIES_MAX = 50_000
ID_MAX = 64

_compteurs: dict[tuple[str, str], dict] = {}


def cle_page(brut: str | None) -> str:
    """Identifiant nettoyé ; absent → un seul budget pour toutes ces pages."""
    return "".join(c for c in (brut or "")[:ID_MAX] if c.isalnum() or c == "-")


def _purger(maintenant: float) -> None:
    for cle in [k for k, v in _compteurs.items() if maintenant - v["vu"] > DUREE_S]:
        del _compteurs[cle]
    while len(_compteurs) >= PAGES_SUIVIES_MAX:
        del _compteurs[min(_compteurs, key=lambda k: _compteurs[k]["vu"])]


def prendre(user_id: str, page: str, **quantites: int) -> str | None:
    """Ajoute `quantites` (texte=, lots=, images=, analyses=, captures=) au
    budget de la page et renvoie None ; ou, si l'une de ces bornes est déjà
    atteinte, renvoie son nom sans rien compter (une quantité 0 vérifie la
    borne sans la consommer). Sans `await` : atomique dans la boucle async."""
    maintenant = time.monotonic()
    cle = (user_id, page)
    compteur = _compteurs.get(cle)
    if compteur is None:
        _purger(maintenant)
        compteur = _compteurs[cle] = {"vu": maintenant, **dict.fromkeys(BORNES, 0)}
    for nom in quantites:
        if compteur[nom] >= BORNES[nom]:
            return nom
    for nom, n in quantites.items():
        compteur[nom] += n
    compteur["vu"] = maintenant
    return None


def ajouter(user_id: str, page: str, **quantites: int) -> None:
    """Compte après coup (image traduite), sans vérifier la borne."""
    compteur = _compteurs.get((user_id, page))
    if compteur is not None:
        for nom, n in quantites.items():
            compteur[nom] += n


def reinitialiser() -> None:
    """Pour les tests."""
    _compteurs.clear()
