"""
Routes documents — CRUD par utilisateur.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Response
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import User, Document, FREE_PLAN
from auth import require_auth
from preview import rasterize_for_trial

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
    """Téléchargement du fichier traduit (ou original si pas encore traduit).

    RÉSERVÉ AUX PLANS PAYANTS quand le fichier est une TRADUCTION. Ce contrôle
    manquait : on avait verrouillé /api/translate/result mais pas cette route,
    et la bibliothèque contournait donc tout le dispositif — un compte d'essai
    téléchargeait sa traduction en clair depuis « Mes documents ». Verrouiller
    une porte et laisser l'autre ouverte ne verrouille rien.

    L'ORIGINAL, lui, reste téléchargeable par tous : c'est le fichier de
    l'utilisateur, il nous l'a confié, on ne va pas le lui rançonner.
    """
    doc = await db.get(Document, doc_id)
    if doc is None or doc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    if doc.translated_path and user.plan == FREE_PLAN:
        raise HTTPException(
            status_code=402,
            detail="Forfait Gratuit : téléchargement indisponible. "
                   "Passez à Starter pour télécharger vos traductions.",
        )

    path = doc.translated_path or doc.original_path
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Fichier introuvable sur le serveur.")

    ext = os.path.splitext(doc.original_name)[1]
    dl_name = doc.original_name.replace(ext, f"_TRADUIT{ext}") if doc.translated_path else doc.original_name

    return FileResponse(path, filename=dl_name)


# ── GET /documents/{id}/preview ──────────────────────────────────────────────

@router.get("/{doc_id}/preview")
async def preview_document(
    doc_id: str,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Aperçu de la traduction — rastérisé et filigrané pour un plan d'essai.

    Sans cette route, « Aperçu » depuis la bibliothèque passait par /download et
    rendait le PDF en clair : la même fuite que sur /partial, par une autre
    porte. Un plan d'essai peut REGARDER sa traduction, jamais en repartir avec
    un document exploitable.
    """
    doc = await db.get(Document, doc_id)
    if doc is None or doc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    path = doc.translated_path or doc.original_path
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Fichier introuvable sur le serveur.")

    with open(path, "rb") as f:
        data = f.read()
    # On ne protège que ce qu'on a PRODUIT : l'original appartient déjà à
    # l'utilisateur, le rastériser ne protégerait rien et coûterait cher.
    if doc.translated_path and user.plan == FREE_PLAN:
        data = rasterize_for_trial(data)
    return Response(content=data, media_type="application/pdf",
                    headers={"Cache-Control": "no-store"})


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
    original_path = doc.original_path
    translated_path = doc.translated_path
    await db.delete(doc)

    # Libérer le quota
    user.storage_used = max(0, user.storage_used - size)
    await db.commit()

    # Nettoyer les fichiers sur disque — UNIQUEMENT ceux qui appartiennent en
    # propre à l'utilisateur (sous `translations/<user_id>/`). Les fichiers
    # d'un document créé à la volée pointent vers le CACHE PARTAGÉ par hash
    # (`translations/<nom>_<hash>/`), commun à tous les comptes ayant traduit le
    # même fichier : un `rmtree` de son dossier parent effacerait les
    # traductions d'autrui (et le job en cours). On ne touche donc qu'aux
    # fichiers strictement contenus dans le dossier privé de l'utilisateur.
    user_root = os.path.realpath(_user_dir(user.id))
    for path in (translated_path, original_path):
        if not path:
            continue
        real = os.path.realpath(path)
        if os.path.commonpath([real, user_root]) == user_root and os.path.isfile(real):
            try:
                os.remove(real)
            except OSError:
                pass

    return {"message": "Document supprimé.", "storage_freed": size}
