"""Documents de TOUS les comptes — RÉSERVÉ à l'admin (`require_admin`).

Pourquoi cet écran existe : quand un utilisateur signale un rendu cassé, l'admin
doit pouvoir retrouver son document et télécharger l'original comme la
traduction pour reproduire le problème, sans lui demander de renvoyer le fichier.

Ce module NE fait que lister et télécharger. Il ne modifie ni ne supprime rien.
Chaque téléchargement est journalisé (qui, quoi, de qui) : l'admin lit des
fichiers qui ne sont pas les siens, il doit en rester une trace.
"""
from __future__ import annotations

import os
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.documents import _lire, _render_or_404
from app.config import logger
from app.core.database import get_db
from app.core.security import require_admin
from app.models import Document, User

router = APIRouter(prefix="/api/admin/documents", tags=["Administration"])

_INTROUVABLE = "Le fichier n'est plus disponible."


def _present(chemin: str | None) -> bool:
    return bool(chemin) and os.path.isfile(chemin)


def _serialize(doc: Document, owner_email: str | None) -> dict:
    return {
        "id": doc.id,
        "original_name": doc.original_name,
        "user_email": owner_email,
        "source_lang": doc.source_lang,
        "target_lang": doc.target_lang,
        "status": doc.status,
        "page_count": doc.page_count,
        "size_bytes": doc.size_bytes,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "has_original": _present(doc.original_path),
        # Le rendu de la traduction a besoin des DEUX fichiers.
        "has_translation": _present(doc.translated_path) and _present(doc.original_path),
    }


def _attachment(data: bytes, filename: str) -> Response:
    """Réponse explicite plutôt que FileResponse : évite les Range/206 qui font
    échouer le fetch côté frontend."""
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition":
                 f"attachment; filename*=UTF-8''{quote(filename, safe='')}"},
    )


async def _charger(db: AsyncSession, doc_id: str) -> tuple[Document, str | None]:
    row = (await db.execute(
        select(Document, User.email)
        .join(User, User.id == Document.user_id)
        .where(Document.id == doc_id)
    )).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    return row[0], row[1]


@router.get("")
async def list_documents(
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Documents de tous les comptes, du plus récent au plus ancien. `q` filtre
    sur l'e-mail du propriétaire ou le nom du fichier (sous-chaîne insensible à
    la casse)."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    conds = []
    if q:
        like = f"%{q}%"
        conds.append(or_(User.email.ilike(like), Document.original_name.ilike(like)))

    stmt = (select(Document, User.email)
            .join(User, User.id == Document.user_id)
            .order_by(Document.created_at.desc())
            .limit(limit).offset(offset))
    count_stmt = (select(func.count()).select_from(Document)
                  .join(User, User.id == Document.user_id))
    if conds:
        stmt = stmt.where(*conds)
        count_stmt = count_stmt.where(*conds)

    rows = (await db.execute(stmt)).all()
    total = await db.scalar(count_stmt)
    return {
        "items": [_serialize(d, email) for d, email in rows],
        "total": total or 0,
    }


@router.get("/{doc_id}/original")
async def download_original(
    doc_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Octets d'origine du document, tels que déposés par son propriétaire."""
    doc, owner_email = await _charger(db, doc_id)
    if not _present(doc.original_path):
        raise HTTPException(status_code=404, detail=_INTROUVABLE)
    data = await run_in_threadpool(_lire, doc.original_path)
    logger.info("admin %s a téléchargé %s du document %s (propriétaire %s)",
                admin.email, "original", doc.id, owner_email)
    return _attachment(data, doc.original_name)


@router.get("/{doc_id}/translated")
async def download_translated(
    doc_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Traduction rendue dans le format du document, comme la reçoit son
    propriétaire sur `/documents/{id}/download` (même nom `_TRADUIT`). Pas de
    contrôle de paiement : l'admin diagnostique, il ne consomme pas.

    `translated_path` ne contient que la traduction stockée (JSON) : on la
    rend depuis l'original, ce qui est aussi ce qu'il faut pour reproduire un
    rendu cassé."""
    doc, owner_email = await _charger(db, doc_id)
    if not _present(doc.translated_path) or not _present(doc.original_path):
        raise HTTPException(status_code=404, detail=_INTROUVABLE)
    ext = os.path.splitext(doc.original_name)[1].lstrip(".").lower()
    data = await run_in_threadpool(_render_or_404, doc, ext)
    base = os.path.splitext(doc.original_name)[0]
    logger.info("admin %s a téléchargé %s du document %s (propriétaire %s)",
                admin.email, "traduction", doc.id, owner_email)
    return _attachment(data, f"{base}_TRADUIT.{ext}")
