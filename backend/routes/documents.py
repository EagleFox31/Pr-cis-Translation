"""
Routes documents — CRUD par utilisateur.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Response
from fastapi.responses import FileResponse
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import User, Document, FREE_PLAN
from auth import require_auth
from preview import rasterize_for_trial

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Le magasin est celui d'`app.py` : `backend/translations`. Cette constante
# valait `os.path.dirname(__file__)` — c'est-à-dire `backend/routes/` — et
# pointait donc sur `backend/routes/translations`, un dossier que la suppression
# créait à chaque appel et qui n'a jamais contenu un seul fichier (mesuré : 0
# ici contre 15 dans le vrai magasin). Le garde-fou de suppression « protégeait »
# les fichiers d'autrui en ne trouvant jamais rien à effacer : aucun octet n'a
# jamais été libéré, et `storage_used` dérivait du disque à chaque suppression.
STORAGE_BASE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "translations",
)


def _inside_store(path: str) -> bool:
    """Le chemin est-il bien DANS le magasin ? Dernier rempart avant `os.remove`.

    `commonpath` lève sur deux volumes différents (Windows) : on refuse alors,
    parce qu'un chemin qu'on ne sait pas situer n'est pas un chemin qu'on efface.
    """
    try:
        real = os.path.realpath(path)
        store = os.path.realpath(STORAGE_BASE)
        return os.path.commonpath([real, store]) == store
    except (ValueError, OSError):
        return False


async def _purge_if_orphan(db: AsyncSession, path: str) -> bool:
    """Efface `path` SI plus aucun Document, de quelque compte que ce soit, n'y
    renvoie.

    Les fichiers vivent dans un magasin PARTAGÉ adressé par le hash du contenu :
    deux comptes ayant déposé le même fichier pointent sur les mêmes octets.
    Effacer sur la seule foi de « mon » Document supprimerait la traduction
    d'autrui. On compte donc les références restantes — la ligne courante est
    déjà supprimée ET commitée, elle ne se compte pas elle-même.
    """
    refs = await db.execute(
        select(func.count()).select_from(Document).where(
            or_(Document.original_path == path, Document.translated_path == path),
        )
    )
    if (refs.scalar() or 0) > 0:
        return False                      # quelqu'un d'autre y tient encore
    if not _inside_store(path):
        return False
    real = os.path.realpath(path)
    if not os.path.isfile(real):
        return False
    try:
        os.remove(real)
    except OSError:
        return False
    _prune_empty_dirs(os.path.dirname(real))
    return True


def _prune_empty_dirs(start: str) -> None:
    """Remonte en effaçant les dossiers VIDES, sans jamais sortir du magasin.

    `os.rmdir` refuse un dossier non vide : c'est notre filet. Un dossier qui
    contient encore un partiel de job survit — tant mieux, on n'a rien à y faire.
    """
    store = os.path.realpath(STORAGE_BASE)
    cur = os.path.realpath(start)
    while cur != store and _inside_store(cur):
        try:
            os.rmdir(cur)                 # lève si non vide : on s'arrête là
        except OSError:
            return
        cur = os.path.dirname(cur)


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


# ── GET /documents/{id}/original ─────────────────────────────────────────────

@router.get("/{doc_id}/original")
async def original_document(
    doc_id: str,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Le fichier SOURCE, tel qu'il a été déposé.

    /download rend la TRADUCTION dès qu'elle existe : impossible d'y récupérer
    la source. L'aperçu depuis la bibliothèque n'avait donc rien à afficher dans
    son panneau de gauche et retombait sur le PDF de DÉMO — on montrait le
    journal d'exemple à côté du CV de l'utilisateur.

    Aucun contrôle de plan : c'est le fichier de l'utilisateur.
    """
    doc = await db.get(Document, doc_id)
    if doc is None or doc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    if not doc.original_path or not os.path.isfile(doc.original_path):
        raise HTTPException(status_code=404, detail="Fichier introuvable sur le serveur.")
    return FileResponse(doc.original_path, filename=doc.original_name)


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

    # Purge par comptage de références. Le commit ci-dessus est INDISPENSABLE
    # avant de compter : tant que la suppression n'est pas validée, la ligne
    # courante se compterait elle-même et rien ne serait jamais orphelin.
    purged = 0
    for path in (translated_path, original_path):
        if path and await _purge_if_orphan(db, path):
            purged += 1

    return {"message": "Document supprimé.", "storage_freed": size,
            "files_purged": purged}
