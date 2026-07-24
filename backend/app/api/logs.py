"""Journal des erreurs — ingestion (front) et administration.

DEUX PUBLICS, DEUX NIVEAUX D'ACCÈS
    * `POST /api/logs/client` est OUVERT : les erreurs d'un visiteur non connecté
      comptent autant que les autres. Il est donc rate-limité et borné en taille.
    * tout le reste est RÉSERVÉ à l'admin (`require_admin`) : lire, exporter,
      marquer traité, supprimer.

CYCLE « consigner puis vider »
    On ne supprime QUE des logs `handled`. La suppression d'un log `new` est
    refusée (409) : l'admin doit d'abord exporter (consigner) et marquer traité.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import case, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import optional_auth, require_admin
from app.models import ErrorLog, LEVELS, STATUS_HANDLED, STATUS_NEW, User
from app.rate_limit import rate_limit_decorator
from app.services.error_log import log_error, maybe_alert_admins

router = APIRouter(prefix="/api/logs", tags=["Journal"])

_MAX_MESSAGE = 2000
_MAX_STACK = 16000
_EXPORT_CAP = 5000    # un export reste un fichier, pas une base entière


class ClientErrorBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=_MAX_MESSAGE)
    stack: str | None = Field(None, max_length=_MAX_STACK)
    level: str = Field("error")
    url: str | None = Field(None, max_length=1000)
    component: str | None = Field(None, max_length=200)
    context: dict | None = None


@router.post("/client")
@rate_limit_decorator("30/minute")
async def ingest_client_error(
    body: ClientErrorBody,
    request: Request,
    user: User | None = Depends(optional_auth),
):
    """Reçoit une erreur de l'interface. Jamais d'échec renvoyé au client : le
    but est de capter, pas d'ajouter une erreur à l'erreur."""
    level = body.level if body.level in LEVELS else "error"
    ctx = dict(body.context or {})
    if body.url:
        ctx.setdefault("url", body.url)
    ctx.setdefault("user_agent", request.headers.get("user-agent", "")[:300])
    await log_error(
        "frontend", body.message, level=level, stack=body.stack, context=ctx,
        location=body.component or body.url or "",
        user_id=(user.id if user else None),
        user_email=(user.email if user else None),
    )
    return {"ok": True}


def _serialize(row: ErrorLog) -> dict:
    return {
        "id": row.id,
        "source": row.source,
        "level": row.level,
        "message": row.message,
        "stack": row.stack,
        "context": row.context,
        "user_email": row.user_email,
        "fingerprint": row.fingerprint,
        "status": row.status,
        "handled_at": row.handled_at.isoformat() if row.handled_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _filtered(source: str | None, level: str | None, status: str | None, q: str | None):
    """Clauses WHERE communes à la liste et à l'export."""
    conds = []
    if source:
        conds.append(ErrorLog.source == source)
    if level:
        conds.append(ErrorLog.level == level)
    if status:
        conds.append(ErrorLog.status == status)
    if q:
        conds.append(ErrorLog.message.ilike(f"%{q}%"))
    return conds


@router.get("")
async def list_groups(
    source: str | None = None,
    level: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Liste REGROUPÉE par empreinte : une ligne par défaut distinct, avec son
    nombre d'occurrences et sa dernière apparition. Le brut se déplie via
    `/group/{fingerprint}`."""
    limit = max(1, min(limit, 200))
    conds = _filtered(source, level, status, q)
    new_count = func.sum(case((ErrorLog.status == STATUS_NEW, 1), else_=0))
    stmt = (
        select(
            ErrorLog.fingerprint,
            ErrorLog.source,
            ErrorLog.level,
            func.max(ErrorLog.message).label("message"),
            func.count().label("count"),
            new_count.label("new_count"),
            func.max(ErrorLog.created_at).label("last_seen"),
            func.min(ErrorLog.created_at).label("first_seen"),
        )
        .group_by(ErrorLog.fingerprint, ErrorLog.source, ErrorLog.level)
        .order_by(func.max(ErrorLog.created_at).desc())
        .limit(limit).offset(offset)
    )
    if conds:
        stmt = stmt.where(*conds)
    rows = (await db.execute(stmt)).all()

    total_groups = await db.scalar(
        select(func.count(func.distinct(ErrorLog.fingerprint)))
        .where(*conds) if conds else
        select(func.count(func.distinct(ErrorLog.fingerprint)))
    )
    return {
        "total_groups": total_groups or 0,
        "groups": [
            {
                "fingerprint": r.fingerprint,
                "source": r.source,
                "level": r.level,
                "message": r.message,
                "count": r.count,
                "new_count": int(r.new_count or 0),
                "status": STATUS_NEW if (r.new_count or 0) > 0 else STATUS_HANDLED,
                "last_seen": r.last_seen.isoformat() if r.last_seen else None,
                "first_seen": r.first_seen.isoformat() if r.first_seen else None,
            }
            for r in rows
        ],
    }


@router.get("/group/{fp}")
async def group_occurrences(
    fp: str,
    limit: int = 100,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    limit = max(1, min(limit, 500))
    rows = (await db.execute(
        select(ErrorLog).where(ErrorLog.fingerprint == fp)
        .order_by(ErrorLog.created_at.desc()).limit(limit)
    )).scalars().all()
    return {"fingerprint": fp, "occurrences": [_serialize(r) for r in rows]}


@router.get("/export")
async def export_logs(
    source: str | None = None,
    level: str | None = None,
    status: str | None = None,
    q: str | None = None,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Télécharge les logs filtrés en JSON — c'est le « consigner sous fichier »
    qui précède la suppression."""
    conds = _filtered(source, level, status, q)
    stmt = select(ErrorLog).order_by(ErrorLog.created_at.desc()).limit(_EXPORT_CAP)
    if conds:
        stmt = stmt.where(*conds)
    rows = (await db.execute(stmt)).scalars().all()
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "logs": [_serialize(r) for r in rows],
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="precis-logs-{stamp}.json"'},
    )


class TargetBody(BaseModel):
    ids: list[str] = Field(default_factory=list)
    fingerprints: list[str] = Field(default_factory=list)


def _target_conds(body: TargetBody):
    conds = []
    if body.ids:
        conds.append(ErrorLog.id.in_(body.ids))
    if body.fingerprints:
        conds.append(ErrorLog.fingerprint.in_(body.fingerprints))
    return conds


@router.post("/handle")
async def mark_handled(
    body: TargetBody,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Marque des logs (par id ou par empreinte) comme traités."""
    conds = _target_conds(body)
    if not conds:
        raise HTTPException(status_code=400, detail="Aucune cible.")
    res = await db.execute(
        update(ErrorLog).where(*conds, ErrorLog.status == STATUS_NEW)
        .values(status=STATUS_HANDLED, handled_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return {"handled": res.rowcount or 0}


@router.delete("")
async def delete_logs(
    body: TargetBody,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Supprime des logs — REFUSÉ si l'un d'eux est encore `new` (409). On ne
    jette que ce qui a été consigné."""
    conds = _target_conds(body)
    if not conds:
        raise HTTPException(status_code=400, detail="Aucune cible.")
    still_new = await db.scalar(
        select(func.count()).select_from(ErrorLog)
        .where(*conds, ErrorLog.status == STATUS_NEW)
    )
    if still_new:
        raise HTTPException(
            status_code=409,
            detail=f"{still_new} log(s) non traité(s) : consigne puis marque traité avant de supprimer.",
        )
    res = await db.execute(delete(ErrorLog).where(*conds))
    await db.commit()
    return {"deleted": res.rowcount or 0}
