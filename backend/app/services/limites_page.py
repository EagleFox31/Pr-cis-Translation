"""Limites par page de l'extension (étude extension-gratuite-forfaits).

L'extension ne débite aucun crédit : elle est limitée par page selon le forfait
de l'utilisateur. La page est un identifiant opaque tiré par l'extension
(en-tête `X-Page`), jamais l'adresse.

Deux niveaux :
- en base (`ExtensionUsage`), permanents : caractères et images traduits par
  page (bornes du forfait, `FORFAITS`) et nombre de pages différentes commencées
  dans la journée UTC. Rien n'expire : une page qui a atteint sa limite la garde ;
- en mémoire (6 h, un seul worker), pour tous les forfaits : les bornes
  techniques qui protègent le serveur (lots, analyses d'image, captures vidéo).
"""
from __future__ import annotations

import hashlib
import time
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExtensionTexteVu, ExtensionUsage, User, utcnow

# Lots de texte : chacun renvoie le prompt et le contexte (défilement infini).
LOTS_MAX = 100
# Images analysées, avec ou sans texte : l'OCR seul, borné plus largement pour
# qu'une page riche en illustrations ne bloque pas ses vraies images à texte.
# Une image à la fois par utilisateur (429 sinon) : la charge reste lissée.
ANALYSES_MAX = 120
# Images de vidéo, prises à la demande sur pause.
CAPTURES_MAX = 20

BORNES = {"lots": LOTS_MAX, "analyses": ANALYSES_MAX, "captures": CAPTURES_MAX}

# Limites de l'extension par forfait ; None = illimité.
# `texte` et `images` : par page, sans limite de temps ; `texte_image` : texte lu
# dans une seule image ; `pages_jour` : pages différentes commencées par jour.
FORFAITS = {
    "free":    {"texte": 30_000, "images": 30, "texte_image": 2_000, "pages_jour": 30},
    "starter": {"texte": 100_000, "images": 80, "texte_image": 4_000, "pages_jour": 150},
    "pro":     {"texte": None, "images": None, "texte_image": None, "pages_jour": 500},
}

DUREE_S = 6 * 3600
PAGES_SUIVIES_MAX = 50_000
ID_MAX = 64

_compteurs: dict[tuple[str, str], dict] = {}


def bornes(plan) -> dict:
    """Limites du forfait : entreprise et administrateur comme Pro, forfait
    inconnu comme Gratuit."""
    if plan in ("enterprise", "admin"):
        plan = "pro"
    return FORFAITS.get(plan, FORFAITS["free"])


def cle_page(brut: str | None) -> str:
    """Identifiant nettoyé ; absent → un seul budget pour toutes ces pages."""
    return "".join(c for c in (brut or "")[:ID_MAX] if c.isalnum() or c == "-")


def _purger(maintenant: float) -> None:
    for cle in [k for k, v in _compteurs.items() if maintenant - v["vu"] > DUREE_S]:
        del _compteurs[cle]
    while len(_compteurs) >= PAGES_SUIVIES_MAX:
        del _compteurs[min(_compteurs, key=lambda k: _compteurs[k]["vu"])]


def prendre(user_id: str, page: str, **quantites: int) -> str | None:
    """Ajoute `quantites` (lots=, analyses=, captures=) au budget technique de
    la page et renvoie None ; ou, si l'une de ces bornes est déjà atteinte,
    renvoie son nom sans rien compter (une quantité 0 vérifie la borne sans la
    consommer). Sans `await` : atomique dans la boucle async."""
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
    """Compte après coup, sans vérifier la borne."""
    compteur = _compteurs.get((user_id, page))
    if compteur is not None:
        for nom, n in quantites.items():
            compteur[nom] += n


def reinitialiser() -> None:
    """Pour les tests."""
    _compteurs.clear()


# ── Compteurs permanents (base) ──────────────────────────────────────────────
def _accorde(demande: int, borne: int | None, pris: int) -> int:
    return demande if borne is None else max(0, min(demande, borne - pris))


async def _pages_du_jour(db: AsyncSession, user_id: str) -> int:
    return (await db.execute(
        select(func.count()).select_from(ExtensionUsage).where(
            ExtensionUsage.user_id == user_id,
            ExtensionUsage.jour == utcnow().date()))).scalar_one()


async def _ligne(db: AsyncSession, user_id: str, page: str,
                 verrou: bool = False) -> ExtensionUsage | None:
    requete = select(ExtensionUsage).where(
        ExtensionUsage.user_id == user_id, ExtensionUsage.page == page
    ).execution_options(populate_existing=True)
    if verrou:
        requete = requete.with_for_update()
    return (await db.execute(requete)).scalar_one_or_none()


async def reserver(db: AsyncSession, user: User, page: str,
                   texte: int = 0, images: int = 0) -> tuple[int, int, str | None]:
    """Réserve, sous verrou, du texte et des images sur la page et commite.
    Rend (texte accordé, images accordées, limite) : l'accord est partiel quand
    la borne du forfait tombe au milieu de la demande ; `limite` vaut alors
    « texte » ou « images » (le premier manque), None si tout est accordé. Une
    page nouvelle au-delà des pages du jour : (0, 0, « pages_jour »). Une page
    déjà commencée, même un autre jour, n'est jamais une page nouvelle."""
    user_id, forfait = user.id, bornes(user.plan)
    # Le verrou de l'utilisateur sérialise les créations de pages : deux
    # requêtes simultanées ne dépassent pas ensemble les pages du jour.
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
    ligne = await _ligne(db, user_id, page, verrou=True)
    if ligne is None and await _pages_du_jour(db, user_id) >= forfait["pages_jour"]:
        # Rien n'a changé : on libère les verrous sans `rollback`, qui périmerait
        # l'objet `user` de l'appelant (accès paresseux impossible en async).
        await db.commit()
        return 0, 0, "pages_jour"
    deja_texte, deja_images = (ligne.caracteres, ligne.images) if ligne else (0, 0)
    texte_ok = _accorde(texte, forfait["texte"], deja_texte)
    images_ok = _accorde(images, forfait["images"], deja_images)
    if texte_ok or images_ok:
        if ligne is None:
            ligne = ExtensionUsage(user_id=user_id, page=page, caracteres=0, images=0,
                                   jour=utcnow().date())
            db.add(ligne)
        ligne.caracteres += texte_ok
        ligne.images += images_ok
    await db.commit()
    limite = ("texte" if texte_ok < texte else "images" if images_ok < images else None)
    return texte_ok, images_ok, limite


async def rendre(db: AsyncSession, user_id: str, page: str,
                 texte: int = 0, images: int = 0) -> None:
    """Retranche ce qui a été réservé et pas utilisé (plancher 0) ; la ligne
    revenue à zéro disparaît : la page n'est plus comptée comme commencée."""
    ligne = await _ligne(db, user_id, page, verrou=True)
    if ligne is not None:
        ligne.caracteres = max(0, ligne.caracteres - texte)
        ligne.images = max(0, ligne.images - images)
        if not ligne.caracteres and not ligne.images:
            await db.delete(ligne)
    await db.commit()


async def verifier(db: AsyncSession, user: User, page: str,
                   images: bool = False) -> str | None:
    """Limite déjà atteinte, sans rien compter : « pages_jour » (page nouvelle et
    pages du jour épuisées) ou, si `images`, « images » ; sinon None."""
    forfait = bornes(user.plan)
    ligne = await _ligne(db, user.id, page)
    if ligne is None and await _pages_du_jour(db, user.id) >= forfait["pages_jour"]:
        return "pages_jour"
    borne = forfait["images"]
    if images and borne is not None and ligne is not None and ligne.images >= borne:
        return "images"
    return None


# ── Textes déjà comptés (empreintes, sans le texte) ──────────────────────────
VUS_JOURS = 30


def empreinte(user_id: str, langue: str, texte: str) -> str:
    return hashlib.sha256(f"{user_id}\0{langue}\0{texte}".encode("utf-8")).hexdigest()


async def deja_vus(db: AsyncSession, user_id: str, langue: str, textes) -> set[str]:
    """Textes que ce compte a déjà fait traduire vers `langue` (30 derniers jours) :
    ils ne sont plus comptés."""
    par_empreinte = {empreinte(user_id, langue, t): t for t in textes}
    if not par_empreinte:
        return set()
    lignes = (await db.execute(select(ExtensionTexteVu.empreinte).where(
        ExtensionTexteVu.user_id == user_id,
        ExtensionTexteVu.empreinte.in_(list(par_empreinte)),
        ExtensionTexteVu.jour >= utcnow().date() - timedelta(days=VUS_JOURS)))).scalars()
    return {par_empreinte[e] for e in lignes}


async def marquer_vus(db: AsyncSession, user_id: str, langue: str, textes) -> None:
    """Garde l'empreinte des textes traduits (jour remis à aujourd'hui) et
    efface celles de plus de 30 jours."""
    aujourdhui = utcnow().date()
    valeurs = [{"user_id": user_id, "empreinte": e, "jour": aujourdhui}
               for e in {empreinte(user_id, langue, t) for t in textes}]
    if valeurs:
        requete = insert(ExtensionTexteVu).values(valeurs)
        await db.execute(requete.on_conflict_do_update(
            index_elements=["user_id", "empreinte"], set_={"jour": aujourdhui}))
    await db.execute(delete(ExtensionTexteVu).where(
        ExtensionTexteVu.user_id == user_id,
        ExtensionTexteVu.jour < aujourdhui - timedelta(days=VUS_JOURS)))
    await db.commit()
