"""Nouveautés : catalogue public, « à voir », abonnement e-mail et désabonnement.

Le désabonnement par lien (`/desabonnement?jeton=`) ne demande pas de
connexion : le jeton signé suffit. Le GET ne fait que LIRE (les antivirus de
messagerie suivent les liens) ; seul le POST désabonne, y compris le POST
« un clic » des messageries (`List-Unsubscribe-Post`).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import langue_ui
from app.content import nouveautes as catalogue
from app.core.database import get_db
from app.core.security import require_auth
from app.models import User
from app.rate_limit import rate_limit_decorator
from app.services.nouveautes import a_voir, langue_de, verifier_jeton

router = APIRouter(prefix="/api/nouveautes", tags=["Nouveautés"])

_JETON_INVALIDE = "Lien de désabonnement invalide."


@router.get("")
async def liste(lang: str = "fr"):
    lang = langue_de(lang)
    return {"version": catalogue.VERSION, "date_version": catalogue.DATE_VERSION,
            "elements": catalogue.elements(lang), "phares": catalogue.phares(lang)}


@router.get("/a-voir")
async def a_voir_route(lang: str | None = None, user: User = Depends(require_auth)):
    return a_voir(user.nouveautes_vues_le, langue_de(lang, user.langue))


@router.post("/vues")
async def marquer_vues(user: User = Depends(require_auth), db: AsyncSession = Depends(get_db)):
    user.nouveautes_vues_le = datetime.now(timezone.utc)
    await db.commit()
    return {"nouveautes_vues_le": user.nouveautes_vues_le.isoformat()}


class AbonnementBody(BaseModel):
    actif: bool
    langue: Literal["fr", "en"] | None = None


@router.put("/abonnement")
async def abonnement(
    body: AbonnementBody,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
    entete: str | None = Depends(langue_ui),
):
    user.abonne_nouveautes = body.actif
    # La date du consentement en est la preuve ; elle n'a plus d'objet après retrait.
    user.abonne_nouveautes_le = datetime.now(timezone.utc) if body.actif else None
    user.langue = body.langue or langue_de(entete, user.langue)
    await db.commit()
    return {"abonne_nouveautes": user.abonne_nouveautes, "langue": user.langue}


async def _compte_du_jeton(jeton: str | None, db: AsyncSession) -> User:
    user_id = verifier_jeton(jeton)
    user = await db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=400, detail=_JETON_INVALIDE)
    return user


@router.get("/desabonnement")
@rate_limit_decorator("30/minute")
async def etat_desabonnement(request: Request, jeton: str | None = None,
                             db: AsyncSession = Depends(get_db)):
    user = await _compte_du_jeton(jeton, db)
    return {"abonne_nouveautes": user.abonne_nouveautes}


@router.post("/desabonnement")
@rate_limit_decorator("30/minute")
async def desabonner(request: Request, jeton: str | None = None,
                     db: AsyncSession = Depends(get_db)):
    user = await _compte_du_jeton(jeton, db)
    user.abonne_nouveautes = False
    user.abonne_nouveautes_le = None
    await db.commit()
    return {"abonne_nouveautes": False}
