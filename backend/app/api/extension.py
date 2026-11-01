"""Routes de l'extension navigateur (étude extension §6).

Rien n'est conservé : ni le texte des pages, ni les images ; seul le débit
entre au registre de consommation (nombre de pages, sans contenu).
L'extension appelle depuis son service de fond (permissions d'hôte) : le
CORS du site n'est pas en jeu.
"""
from __future__ import annotations

import base64

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
from app.services.ocr_v2.detect import LectureEchouee
from app.services.ocr_v2.image import OCTETS_MAX, ImageRefusee, traduire_image, verifier

router = APIRouter(prefix="/api/extension", tags=["Extension"])

# Une image à la fois par utilisateur (étude §6) : l'OCR occupe un cœur.
_en_cours: set[str] = set()

_REFUS = {"taille": 413, "pixels": 413, "type": 415, "animee": 415}


class Segments(BaseModel):
    textes: list[str]
    langue: str = "fr"


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
    if len(textes) > ext.SEGMENTS_MAX or sum(map(len, textes)) > ext.CARACTERES_MAX:
        raise HTTPException(status_code=413, detail="Trop de texte pour un seul appel.")
    pages = ext.pages_pour_segments(textes)
    if not ext.couvre(*(await ext.couverture(db, current_user))[:2], pages):
        return _manque(pages)
    try:
        traductions = await run_in_threadpool(ext.traduire_textes, textes, corps.langue)
    except ext.TraductionIndisponible as e:
        logger.warning(f"Extension, segments non traduits : {e}")
        raise HTTPException(status_code=503, detail="Traduction indisponible. Réessayez.")
    if not await ext.debiter(db, current_user.id, pages):
        return _manque(pages)
    return {"traductions": traductions, "pages": pages}


@router.post("/image")
@rate_limit_decorator("30/minute")
async def traduire_une_image(request: Request, file: UploadFile = File(...),
                             langue: str = Form("fr"),
                             current_user: User = Depends(require_auth),
                             db: AsyncSession = Depends(get_db)):
    data = await file.read(OCTETS_MAX + 1)
    try:
        verifier(data)
    except ImageRefusee as e:
        raise HTTPException(status_code=_REFUS[e.code], detail=f"Image refusée : {e.code}.")
    if not ext.couvre(*(await ext.couverture(db, current_user))[:2], 1):
        return _manque(1)
    if current_user.id in _en_cours:
        raise HTTPException(status_code=429, detail="Une image est déjà en cours.")
    _en_cours.add(current_user.id)
    try:
        rendu = await run_in_threadpool(
            traduire_image, data, lambda t: ext.traduire_textes(t, langue))
    except (LectureEchouee, ext.TraductionIndisponible) as e:
        logger.warning(f"Extension, image non traduite : {e}")
        raise HTTPException(status_code=503, detail="Image non traduite. Réessayez.")
    finally:
        _en_cours.discard(current_user.id)
    # Honnêteté : une image non remplacée n'est ni rendue modifiée ni débitée.
    if rendu.remplacee and not await ext.debiter(db, current_user.id, 1):
        return _manque(1)
    return {
        "remplacee": rendu.remplacee,
        "pages": 1 if rendu.remplacee else 0,
        "mime": rendu.mime,
        "image": base64.b64encode(rendu.data).decode() if rendu.remplacee else None,
        "blocs": [{"texte": b.texte, "traduction": b.traduction,
                   "boite": list(b.boite), "remplace": b.remplace} for b in rendu.blocs],
    }
