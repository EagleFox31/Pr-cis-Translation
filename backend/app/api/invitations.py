"""Invitations — un compte connecté invite des proches à découvrir Précis.

GARDE-FOUS
    Chaque envoi part de NOTRE domaine vers une adresse choisie par
    l'utilisateur : sans bornes, c'est un relais de spam. D'où :
      * au plus `_MAX_PAR_REQUETE` adresses par envoi, `_QUOTA_JOUR` par jour ;
      * une adresse déjà invitée (par qui que ce soit) il y a moins de
        `_FENETRE_DOUBLON` n'en reçoit pas une seconde ;
      * une adresse qui a DÉJÀ un compte est ignorée.
    Le quota se compte sous un verrou par compte (PostgreSQL) : des envois
    simultanés ne le dépassent pas. Les e-mails partent après la réponse
    (`app.services.invitations`), pour que sa durée ne trahisse rien.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import langue_ui
from app.core.database import get_db
from app.core.security import require_auth
from app.models import Invitation, User
from app.models.base import new_uuid
from app.services import anti_abus
from app.rate_limit import rate_limit_decorator
from app.services.invitations import envoyer_invitations

router = APIRouter(prefix="/api/invitations", tags=["Invitations"])

_MAX_PAR_REQUETE = 10
_QUOTA_JOUR = 20
_FENETRE_DOUBLON = timedelta(days=7)
_MAX_MESSAGE = 500
class InvitationBody(BaseModel):
    emails: list[EmailStr] = Field(..., min_length=1, max_length=_MAX_PAR_REQUETE)
    message: str | None = Field(None, max_length=_MAX_MESSAGE)


@router.post("")
@rate_limit_decorator("5/minute")
async def inviter(
    request: Request,
    body: InvitationBody,
    taches: BackgroundTasks,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
    langue: str | None = Depends(langue_ui),
):
    maintenant = datetime.now(timezone.utc)
    soi = user.email.strip().lower()
    # Normalisées, dédoublonnées, ordre de saisie conservé ; soi-même exclu.
    adresses = [a for a in dict.fromkeys(str(e).strip().lower() for e in body.emails)
                if a != soi]
    if not adresses:
        raise HTTPException(status_code=422, detail="Aucune adresse à inviter.")
    jetables = [a for a in adresses if anti_abus.is_disposable(a)]
    if jetables:
        raise HTTPException(400, f"{anti_abus.DISPOSABLE_MESSAGE} ({', '.join(jetables)})")

    if db.bind.dialect.name == "postgresql":
        # Tenu jusqu'au commit : deux envois simultanés du même compte se
        # comptent l'un après l'autre.
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
                         {"k": f"invitations:{user.id}"})
    deja = await db.scalar(
        select(func.count()).select_from(Invitation).where(
            Invitation.inviter_id == user.id,
            Invitation.created_at >= maintenant - timedelta(days=1)))
    restant = _QUOTA_JOUR - (deja or 0)
    if restant < len(adresses):
        raise HTTPException(
            status_code=429,
            detail=f"Limite quotidienne atteinte : encore {max(restant, 0)} "
                   f"invitation(s) possible(s) aujourd'hui.")

    inscrits = set((await db.scalars(
        select(func.lower(User.email)).where(func.lower(User.email).in_(adresses)))).all())
    recentes = set((await db.scalars(
        select(Invitation.email).where(
            Invitation.email.in_(adresses),
            Invitation.created_at >= maintenant - _FENETRE_DOUBLON))).all())

    message = (body.message or "").strip() or None
    inviteur = (user.name or "").strip() or user.email
    reservees = [(new_uuid(), a) for a in adresses
                 if a not in inscrits and a not in recentes]
    for inv_id, adresse in reservees:
        db.add(Invitation(id=inv_id, inviter_id=user.id, email=adresse))
    await db.commit()
    if reservees:
        taches.add_task(envoyer_invitations, reservees, inviteur, user.email,
                        message, langue)
    # Volontairement le nombre d'adresses TRAITÉES, pas d'envois réels : la
    # réponse ne doit rien révéler des comptes existants.
    return {"ok": True, "count": len(adresses)}
