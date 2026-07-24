"""Assistance — les utilisateurs écrivent, l'admin traite.

DEUX PUBLICS, DEUX NIVEAUX D'ACCÈS
    * `POST /api/support` est réservé aux comptes CONNECTÉS (`require_auth`) : un
      ticket est rattaché à quelqu'un à qui répondre. Rate-limité, tailles bornées.
    * le reste est RÉSERVÉ à l'admin (`require_admin`) : lister, traiter, supprimer.

CYCLE « ouvert → traité »
    On ne supprime QUE des tickets `handled` (409 sinon) : un ticket ouvert, c'est
    quelqu'un qui attend encore. On traite d'abord, on efface ensuite.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ADMIN_ALERT_EMAIL, logger
from app.core.database import get_db
from app.core.email import send_plain
from app.core.security import require_admin, require_auth
from app.models import (CATEGORIES, STATUS_OPEN, SupportTicket, TICKET_HANDLED,
                        User)
from app.rate_limit import rate_limit_decorator

router = APIRouter(prefix="/api/support", tags=["Assistance"])

_MAX_SUBJECT = 200
_MAX_MESSAGE = 5000


class TicketBody(BaseModel):
    category: str = Field("problem")
    subject: str = Field(..., min_length=1, max_length=_MAX_SUBJECT)
    message: str = Field(..., min_length=1, max_length=_MAX_MESSAGE)
    url: str | None = Field(None, max_length=1000)
    # Document concerné, référencé AUTOMATIQUEMENT par le frontend (aperçu /
    # bibliothèque). L'id peut manquer (aperçu d'une traduction fraîche) ; le nom
    # suffit à savoir de quel document il s'agit. On ne le CROIT pas : c'est un
    # repère pour l'admin, pas une clé de droits.
    document_id: str | None = Field(None, max_length=64)
    document_name: str | None = Field(None, max_length=300)


async def _notify_admins(db: AsyncSession, ticket: SupportTicket) -> None:
    """Prévient l'admin qu'un ticket est arrivé — au mieux, jamais bloquant.

    Destinataires : les comptes `admin` en base, plus `ADMIN_ALERT_EMAIL` en
    repli si aucun n'existe encore (bootstrap). L'échec d'envoi ne doit JAMAIS
    faire échouer la création du ticket : le ticket est déjà en base, c'est lui
    qui compte."""
    try:
        rows = (await db.execute(
            select(User.email).where(User.plan == "admin")
        )).scalars().all()
        recipients = [e for e in rows if e] or (
            [ADMIN_ALERT_EMAIL] if ADMIN_ALERT_EMAIL else [])
        if not recipients:
            return
        body = (f"Nouveau ticket ({ticket.category}) de "
                f"{ticket.user_email or 'inconnu'} :\n\n"
                f"{ticket.subject}\n\n{ticket.message}")
        for to in recipients:
            await send_plain(to, f"[Support] {ticket.subject}", body)
    except Exception as e:
        logger.warning("Alerte support non envoyée : %s", e)


@router.post("")
@rate_limit_decorator("10/minute")
async def create_ticket(
    body: TicketBody,
    request: Request,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Enregistre une demande d'assistance et alerte l'admin."""
    category = body.category if body.category in CATEGORIES else "problem"
    ctx: dict = {"plan": user.plan}
    if body.url:
        ctx["url"] = body.url
    if body.document_id:
        ctx["document_id"] = body.document_id
    if body.document_name:
        ctx["document_name"] = body.document_name
    ctx["user_agent"] = request.headers.get("user-agent", "")[:300]

    ticket = SupportTicket(
        category=category, subject=body.subject.strip(),
        message=body.message.strip(), context=ctx,
        user_id=user.id, user_email=user.email, status=STATUS_OPEN,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    await _notify_admins(db, ticket)
    return {"ok": True, "id": ticket.id}


def _serialize(t: SupportTicket) -> dict:
    return {
        "id": t.id,
        "category": t.category,
        "subject": t.subject,
        "message": t.message,
        "context": t.context,
        "user_email": t.user_email,
        "status": t.status,
        "admin_note": t.admin_note,
        "handled_at": t.handled_at.isoformat() if t.handled_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("")
async def list_tickets(
    category: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Liste des tickets, du plus récent au plus ancien."""
    limit = max(1, min(limit, 200))
    conds = []
    if category:
        conds.append(SupportTicket.category == category)
    if status:
        conds.append(SupportTicket.status == status)
    if q:
        like = f"%{q}%"
        conds.append(or_(SupportTicket.subject.ilike(like),
                         SupportTicket.message.ilike(like),
                         SupportTicket.user_email.ilike(like)))

    stmt = (select(SupportTicket)
            .order_by(SupportTicket.created_at.desc())
            .limit(limit).offset(offset))
    if conds:
        stmt = stmt.where(*conds)
    rows = (await db.execute(stmt)).scalars().all()

    count_stmt = select(func.count()).select_from(SupportTicket)
    if conds:
        count_stmt = count_stmt.where(*conds)
    total = await db.scalar(count_stmt)

    open_count = await db.scalar(
        select(func.count()).select_from(SupportTicket)
        .where(SupportTicket.status == STATUS_OPEN)
    )
    return {
        "total": total or 0,
        "open_count": open_count or 0,
        "tickets": [_serialize(t) for t in rows],
    }


class HandleBody(BaseModel):
    ids: list[str] = Field(default_factory=list)
    note: str | None = Field(None, max_length=_MAX_MESSAGE)


@router.post("/handle")
async def handle_tickets(
    body: HandleBody,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Marque des tickets comme traités, avec une note interne facultative."""
    if not body.ids:
        raise HTTPException(status_code=400, detail="Aucune cible.")
    values: dict = {"status": TICKET_HANDLED,
                    "handled_at": datetime.now(timezone.utc)}
    if body.note:
        values["admin_note"] = body.note.strip()
    res = await db.execute(
        update(SupportTicket).where(SupportTicket.id.in_(body.ids)).values(**values)
    )
    await db.commit()
    return {"handled": res.rowcount or 0}


class DeleteBody(BaseModel):
    ids: list[str] = Field(default_factory=list)


@router.delete("")
async def delete_tickets(
    body: DeleteBody,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Supprime des tickets — REFUSÉ si l'un est encore `open` (409). On ne jette
    que ce qui a été traité."""
    if not body.ids:
        raise HTTPException(status_code=400, detail="Aucune cible.")
    still_open = await db.scalar(
        select(func.count()).select_from(SupportTicket)
        .where(SupportTicket.id.in_(body.ids), SupportTicket.status == STATUS_OPEN)
    )
    if still_open:
        raise HTTPException(
            status_code=409,
            detail=f"{still_open} ticket(s) non traité(s) : traite-les avant de supprimer.",
        )
    res = await db.execute(
        delete(SupportTicket).where(SupportTicket.id.in_(body.ids))
    )
    await db.commit()
    return {"deleted": res.rowcount or 0}
