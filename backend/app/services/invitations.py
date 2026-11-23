"""Invitations : envoi après la réponse, et purge des traces anciennes.

POURQUOI APRÈS LA RÉPONSE
    Une adresse inscrite ou déjà invitée est écartée sans appel SMTP. Si la
    route attendait les envois, son temps de réponse dirait laquelle a un
    compte. Les traces sont donc réservées (et validées) AVANT, l'envoi part en
    tâche de fond, et la trace d'un envoi raté est effacée : l'adresse pourra
    être réinvitée, et le quota rendu.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import logger
from app.core import email as courriel
from app.models import Invitation

# Le quota porte sur un jour, l'anti-doublon sur sept : au-delà, une trace n'a
# plus d'usage et l'adresse d'un tiers n'a pas à être gardée (RGPD).
CONSERVATION = timedelta(days=30)


async def purger_invitations(db: AsyncSession) -> int:
    """Efface les traces plus vieilles que `CONSERVATION`. Ne valide pas :
    l'appelant décide du commit."""
    limite = datetime.now(timezone.utc) - CONSERVATION
    r = await db.execute(delete(Invitation).where(Invitation.created_at < limite))
    return r.rowcount or 0


async def envoyer_invitations(reservees: list[tuple[str, str]], inviteur: str,
                              inviteur_email: str, message: str | None,
                              langue: str | None) -> None:
    """Envoie chaque invitation réservée (`(id, adresse)`), puis efface les
    traces des envois ratés et purge les anciennes."""
    from app.core.database import async_session

    rates = []
    for inv_id, adresse in reservees:
        try:
            await courriel.send_invitation_email(adresse, inviteur, inviteur_email,
                                                 message, langue)
        except courriel.EmailIndisponible:
            rates.append(inv_id)
    try:
        async with async_session() as db:
            if rates:
                await db.execute(delete(Invitation).where(Invitation.id.in_(rates)))
            await purger_invitations(db)
            await db.commit()
    except Exception as e:
        logger.warning(f"Ménage des invitations impossible : {e}")
    logger.info("Invitations de %s : %d envoi(s), %d échec(s)",
                inviteur_email, len(reservees), len(rates))
