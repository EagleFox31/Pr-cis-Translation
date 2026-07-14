"""
Routes documents — CRUD par utilisateur.
"""
from __future__ import annotations
import os
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import User, Document
from auth import require_auth

router = APIRouter(prefix="/api/documents", tags=["documents"])

STORAGE_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translations")


def _user_dir(user_id: str) -> str:
    p = os.path.join(STORAGE_BASE, user_id)
    os.makedirs(p, exist_ok=True)
    return p


def _doc_response(doc: Document) -> dict:
    return {
        "id": doc.id,
        "original_name": doc.original_name,
        "source_lang": doc.source_lang,
        "target_lang": doc.target_lang,
        "size_bytes": doc.size_bytes,
        "status": doc.status,
        "page_count": doc.page_count,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


# ── GET /documents ───────────────────────────────────────────────────────────

@router.get("")
async def list_documents(
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Liste les documents de l'utilisateur connecté, du plus récent au plus ancien."""
    stmt = (
        select(Document)
        .where(Document.user_id == user.id)
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(stmt)
    docs = result.scalars().all()
    return [_doc_response(d) for d in docs]


# ── GET /documents/{id} ─────────────────────────────────────────────────────

@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Métadonnées d'un document."""
    doc = await db.get(Document, doc_id)
    if doc is None or doc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    return _doc_response(doc)


# ── GET /documents/{id}/download ─────────────────────────────────────────────

@router.get("/{doc_id}/download")
async def download_document(
    doc_id: str,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Téléchargement du fichier traduit (ou original si pas encore traduit)."""
    doc = await db.get(Document, doc_id)
    if doc is None or doc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    path = doc.translated_path or doc.original_path
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Fichier introuvable sur le serveur.")

    ext = os.path.splitext(doc.original_name)[1]
    dl_name = doc.original_name.replace(ext, f"_TRADUIT{ext}") if doc.translated_path else doc.original_name

    return FileResponse(path, filename=dl_name)


# ── DELETE /documents/{id} ───────────────────────────────────────────────────

@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Supprime un document et ses fichiers."""
    doc = await db.get(Document, doc_id)
    if doc is None or doc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    size = doc.size_bytes
    await db.delete(doc)

    # Libérer le quota
    user.storage_used = max(0, user.storage_used - size)
    await db.commit()

    # Nettoyer les fichiers sur disque
    doc_dir = os.path.dirname(doc.original_path)
    if os.path.isdir(doc_dir):
        shutil.rmtree(doc_dir, ignore_errors=True)

    return {"message": "Document supprimé.", "storage_freed": size}
