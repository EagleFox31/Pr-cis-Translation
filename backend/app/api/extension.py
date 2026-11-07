"""Routes de l'extension navigateur (étude extension §6).

Le texte des pages n'est pas conservé. Les images traduites (hors vidéo)
entrent 30 jours dans un cache partagé, retrouvable seulement en renvoyant
la même image (services/cache_images.py, étude vitesse-images-extension) ;
le débit entre au registre de consommation (nombre de pages, sans contenu).
L'extension appelle depuis son service de fond (permissions d'hôte) : le
CORS du site n'est pas en jeu.
"""
from __future__ import annotations

import base64
import hashlib
import time
from collections import OrderedDict

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import logger
from app.core.database import get_db
from app.core.security import require_auth
from app.models import User
from app.rate_limit import rate_limit_decorator
from app.services import extension as ext
from app.services import cache_images, limites_page
from app.services.ocr_v2.detect import LectureEchouee
from app.services.ocr_v2.image import OCTETS_MAX, ImageRefusee, traduire_image, verifier

router = APIRouter(prefix="/api/extension", tags=["Extension"])

# Deux images à la fois par utilisateur (étude vitesse-images-extension ;
# auparavant une seule, étude §6) : chacune occupe un cœur pour l'OCR.
PARALLELE = 2
_en_cours: dict[str, int] = {}

_REFUS = {"taille": 413, "pixels": 413, "type": 415, "animee": 415}


class Segments(BaseModel):
    textes: list[str]
    langue: str = "fr"
    titre: str = ""
    contexte: list[str] = []


def _page(request: Request) -> str:
    return limites_page.cle_page(request and request.headers.get("x-page"))


def _limite(request: Request, user: User, **quantites):
    """413 si la page a épuisé son budget (étude limites-page-extension)."""
    nom = limites_page.prendre(user.id, _page(request), **quantites)
    if nom is None:
        return None
    return JSONResponse(status_code=413, content={
        "reason": "page_limit", "limite": nom,
        "detail": "Limite atteinte pour cette page.",
    })


def _manque(pages):
    return JSONResponse(status_code=402, content={
        "reason": "need_credits", "pages_needed": pages,
        "detail": "Crédits insuffisants pour cette traduction.",
    })


@router.post("/segments")
@rate_limit_decorator("60/minute")
async def traduire_segments(request: Request, corps: Segments,
                            current_user: User = Depends(require_auth),
                            db: AsyncSession = Depends(get_db)):
    textes = corps.textes
    if not textes:
        return {"traductions": [], "pages": 0}
    if (len(textes) > ext.SEGMENTS_MAX or sum(map(len, textes)) > ext.CARACTERES_MAX
            or len(corps.titre) + sum(map(len, corps.contexte)) > ext.CONTEXTE_MAX):
        raise HTTPException(status_code=413, detail="Trop de texte pour un seul appel.")
    pages = ext.pages_pour_segments(textes, current_user.extension_avance)
    if pages and not ext.couvre(*(await ext.couverture(db, current_user))[:2], pages):
        return _manque(pages)
    if refus := _limite(request, current_user, texte=sum(map(len, textes)), lots=1):
        return refus
    try:
        traductions = await run_in_threadpool(
            ext.traduire_textes, textes, corps.langue, None, corps.titre, corps.contexte)
    except ext.TraductionIndisponible as e:
        logger.warning(f"Extension, segments non traduits : {e}")
        raise HTTPException(status_code=503, detail="Traduction indisponible. Réessayez.")
    debitees = await ext.debiter_texte(db, current_user.id, ext.caracteres(textes))
    if debitees is None:
        return _manque(pages)
    return {"traductions": traductions, "pages": debitees}


# Rendus récents (analyse puis traduction) : l'image analysée se traduit
# ensuite sans refaire l'OCR (étude analyse-images-extension). Un seul worker.
# Propres à chaque compte : un rendu incomplet ne passe pas d'un compte à l'autre.
RECENTS_MAX = 64
RECENTS_S = 15 * 60
_recents: OrderedDict[str, tuple[float, dict]] = OrderedDict()


def _cle_recente(user: User, data: bytes, langue: str) -> str:
    return f"{user.id}-{hashlib.sha256(data).hexdigest()}-{langue}"


def _recent(cle: str) -> dict | None:
    entree = _recents.get(cle)
    if entree is None or time.monotonic() - entree[0] > RECENTS_S:
        _recents.pop(cle, None)
        return None
    return entree[1]


def _garder(cle: str, rendu: dict) -> None:
    maintenant = time.monotonic()
    _recents[cle] = (maintenant, rendu)
    _recents.move_to_end(cle)
    # Les plus anciennes en tête : les expirées partent sans attendre d'être relues.
    while _recents and maintenant - next(iter(_recents.values()))[0] > RECENTS_S:
        _recents.popitem(last=False)
    while len(_recents) > RECENTS_MAX:
        _recents.popitem(last=False)


async def _lire_image(file: UploadFile) -> bytes:
    data = await file.read(OCTETS_MAX + 1)
    try:
        verifier(data)
    except ImageRefusee as e:
        raise HTTPException(status_code=_REFUS[e.code], detail=f"Image refusée : {e.code}.")
    return data


def _place_libre(user: User) -> None:
    """429 avant de compter le budget : la reprise ne le consomme pas deux fois."""
    if _en_cours.get(user.id, 0) >= PARALLELE:
        raise HTTPException(status_code=429, detail="Deux images sont déjà en cours.")


async def _produire(user: User, data: bytes, langue: str, cle: str | None) -> dict:
    """OCR, traduction et rendu, deux à la fois par utilisateur ; sans débit."""
    _place_libre(user)
    _en_cours[user.id] = _en_cours.get(user.id, 0) + 1
    try:
        rendu = await run_in_threadpool(
            traduire_image, data, lambda t: ext.traduire_textes(t, langue))
    except (LectureEchouee, ext.TraductionIndisponible) as e:
        logger.warning(f"Extension, image non traduite : {e}")
        raise HTTPException(status_code=503, detail="Image non traduite. Réessayez.")
    finally:
        if (n := _en_cours.pop(user.id, 1) - 1) > 0:
            _en_cours[user.id] = n
    logger.info("Extension, image : " + ", ".join(
        f"{k} {v:.1f} s" for k, v in rendu.durees.items()))
    blocs = [{"texte": b.texte, "traduction": b.traduction,
              "boite": list(b.boite), "remplace": b.remplace} for b in rendu.blocs]
    if rendu.remplacee and rendu.complet and cle:
        await run_in_threadpool(cache_images.ecrire, cle, rendu.mime, blocs, rendu.data)
    return {"remplacee": rendu.remplacee, "mime": rendu.mime,
            "image": rendu.data if rendu.remplacee else None, "blocs": blocs}


@router.post("/image/analyse")
@rate_limit_decorator("60/minute")
async def analyser_une_image(request: Request, file: UploadFile = File(...),
                             langue: str = Form("fr"),
                             current_user: User = Depends(require_auth),
                             db: AsyncSession = Depends(get_db)):
    """Traduisible ou non, sans débit ni contenu renvoyé : l'accord n'annonce
    que les images réellement traduisibles."""
    data = await _lire_image(file)
    if not ext.couvre(*(await ext.couverture(db, current_user))[:2], 1):
        return _manque(1)
    recente = _cle_recente(current_user, data, langue)
    if (connu := _recent(recente)) is not None:
        return {"traduisible": connu["remplacee"]}
    cle = cache_images.cle(data, langue) if cache_images.ACTIF else None
    if cle and await run_in_threadpool(cache_images.lire, cle):
        return {"traduisible": True}
    _place_libre(current_user)
    if refus := _limite(request, current_user, analyses=1, images=0):
        return refus
    rendu = await _produire(current_user, data, langue, cle)
    _garder(recente, rendu)
    return {"traduisible": rendu["remplacee"]}


@router.post("/image")
# 60 : les images déjà en cache reviennent en quelques ms, deux à la fois.
@rate_limit_decorator("60/minute")
async def traduire_une_image(request: Request, file: UploadFile = File(...),
                             langue: str = Form("fr"), video: bool = Form(False),
                             current_user: User = Depends(require_auth),
                             db: AsyncSession = Depends(get_db)):
    data = await _lire_image(file)
    if not ext.couvre(*(await ext.couverture(db, current_user))[:2], 1):
        return _manque(1)
    # Seules les images traduites usent le budget « images » ; chaque analyse
    # consomme le budget « analyses », plus large.
    quantites = {"captures": 1} if video is True else {"analyses": 1, "images": 0}
    cle = cache_images.cle(data, langue) if cache_images.ACTIF and video is not True else None
    recente = _cle_recente(current_user, data, langue) if video is not True else None
    if recente and (connu := _recent(recente)) is not None:
        # Déjà analysée : l'OCR a été compté à l'analyse.
        quantites = {"images": 0}
        rendu = connu
    elif cle and (connue := await run_in_threadpool(cache_images.lire, cle)):
        # Déjà traduite : même débit et même budget, sans OCR ni traduction.
        rendu = {"remplacee": True, "mime": connue["mime"], "image": connue["image"],
                 "blocs": connue["blocs"]}
    else:
        rendu = None
    if rendu is None:
        _place_libre(current_user)
        if refus := _limite(request, current_user, **quantites):
            return refus
        rendu = await _produire(current_user, data, langue, cle)
    elif refus := _limite(request, current_user, **quantites):
        return refus
    # Honnêteté : une image non remplacée n'est ni rendue modifiée ni débitée.
    if rendu["remplacee"]:
        if video is not True:
            # Compté avant le débit : deux envois simultanés ne dépassent pas le budget.
            limites_page.ajouter(current_user.id, _page(request), images=1)
        if not await ext.debiter(db, current_user.id, 1):
            return _manque(1)
    return {
        "remplacee": rendu["remplacee"],
        "pages": 1 if rendu["remplacee"] else 0,
        "mime": rendu["mime"],
        "image": base64.b64encode(rendu["image"]).decode() if rendu["remplacee"] else None,
        "blocs": rendu["blocs"],
    }
