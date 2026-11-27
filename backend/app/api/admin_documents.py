"""Documents de TOUS les comptes — RÉSERVÉ à l'admin (`require_admin`).

Pourquoi cet écran existe : quand un utilisateur signale un rendu cassé, l'admin
doit pouvoir retrouver son document et télécharger l'original comme la
traduction pour reproduire le problème, sans lui demander de renvoyer le fichier.

Ce module liste, télécharge et affiche (aperçu original | traduction). Il ne
modifie ni ne supprime jamais le document d'un client. Seule écriture : « Créer
ma copie », qui ajoute une fiche au nom de l'admin vers les mêmes fichiers.
Chaque lecture est journalisée (qui, quoi, de qui) : l'admin lit des fichiers
qui ne sont pas les siens, il doit en rester une trace.
"""
from __future__ import annotations

import os
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.documents import _lire, _render_or_404, _rendu_pdf_complet
from app.config import logger
from app.core.database import get_db
from app.core.security import require_admin
from app.models import Document, User
from app.services.documents import copie_du_document as _copie_du_document
from app.services.office import convert_to_pdf_bytes, tour_conversion

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
        "copie_de": doc.copie_de,
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
        conds.append(or_(User.email.icontains(q, autoescape=True), Document.original_name.icontains(q, autoescape=True)))

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


def _pdf(data: bytes) -> Response:
    """PDF à afficher dans la modale d'aperçu : jamais mis en cache côté client."""
    return Response(content=data, media_type="application/pdf",
                    headers={"Cache-Control": "no-store"})


@router.get("/{doc_id}/source-pdf")
async def source_pdf(
    doc_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Original converti en PDF, pour le panneau de gauche de l'aperçu. Même
    conversion que `/documents/{id}/original?as=pdf` ; `/original`, lui, reste
    le téléchargement des octets d'origine."""
    doc, owner_email = await _charger(db, doc_id)
    if not _present(doc.original_path):
        raise HTTPException(status_code=404, detail=_INTROUVABLE)
    data = await run_in_threadpool(_lire, doc.original_path)
    ext = os.path.splitext(doc.original_name)[1].lstrip(".").lower()
    if ext != "pdf":
        try:
            async with tour_conversion(data, ext) as tour_pris:
                data = await run_in_threadpool(convert_to_pdf_bytes, data, ext,
                                               tour_pris=tour_pris)
        except Exception:
            logger.exception("Conversion de l'original impossible (doc %s)", doc.id)
            raise HTTPException(
                status_code=500,
                detail="La conversion du document source pour l'aperçu a échoué.")
    logger.info("admin %s a affiché %s du document %s (propriétaire %s)",
                admin.email, "l'original (PDF)", doc.id, owner_email)
    return _pdf(data)


@router.get("/{doc_id}/apercu")
async def apercu_traduction(
    doc_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Traduction rendue EN ENTIER et EN CLAIR, en PDF, pour l'aperçu admin.
    Ni filigrane ni contrôle de paiement : l'admin diagnostique, il ne consomme
    pas. Le rendu passe par le même cache que l'aperçu du client."""
    doc, owner_email = await _charger(db, doc_id)
    if not _present(doc.translated_path) or not _present(doc.original_path):
        raise HTTPException(status_code=404, detail=_INTROUVABLE)
    ext = os.path.splitext(doc.original_name)[1].lstrip(".").lower()
    data = await run_in_threadpool(_rendu_pdf_complet, doc, ext, doc.translated_path)
    logger.info("admin %s a affiché %s du document %s (propriétaire %s)",
                admin.email, "la traduction (PDF)", doc.id, owner_email)
    return _pdf(data)


@router.post("/{doc_id}/copie")
async def creer_copie(
    doc_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Photo de la traduction d'un client, au nom de l'admin.

    La copie pointe vers les MÊMES fichiers que le document du client (rien
    n'est dupliqué, hors la traduction : elle reçoit la sienne, `_d<id>`), si
    bien que les retouches du client n'y changent rien et qu'elle survit à la
    suppression de son document (la purge compte les références).

    Idempotent : une seconde demande renvoie la copie déjà faite.
    """
    doc, owner_email = await _charger(db, doc_id)
    if doc.status != "done":
        raise HTTPException(status_code=409,
                            detail="Ce document n'est pas encore traduit.")
    if not _present(doc.translated_path) or not _present(doc.original_path):
        raise HTTPException(status_code=404, detail=_INTROUVABLE)
    if doc.user_id == admin.id:
        raise HTTPException(status_code=400,
                            detail="Ce document est déjà dans votre bibliothèque.")
    if doc.copie_de:
        # Copie d'une copie : le lien vers le document du client serait perdu.
        raise HTTPException(status_code=400,
                            detail="Ce document est déjà une copie d'admin.")

    existante = (await db.execute(
        select(Document.id).where(Document.user_id == admin.id,
                                  Document.copie_de == doc.id)
    )).scalars().first()
    if existante:
        return {"id": existante, "cree": False}

    # Champ par champ : tout ce qui décrit le document est repris ; rien de ce
    # qui facture. `storage_charged` à 0 (le quota de l'admin n'est pas touché),
    # `paid` vrai pour qu'il le voie en clair.
    nouveau = Document(
        user_id=admin.id, copie_de=doc.id,
        original_name=doc.original_name,
        source_lang=doc.source_lang, target_lang=doc.target_lang,
        original_path=doc.original_path, translated_path=doc.translated_path,
        size_bytes=doc.size_bytes, storage_charged=0,
        status="done", page_count=doc.page_count, pages_done=doc.pages_done,
        paid=True, reglages=doc.reglages,
    )
    # Un seul enregistrement, une fois la photo faite : jamais de copie qui
    # viserait encore la traduction du client (`flush` fournit l'identifiant
    # qui nomme la photo).
    db.add(nouveau)
    await db.flush()

    try:
        copie = await run_in_threadpool(_copie_du_document, nouveau)
    except OSError:
        logger.exception("Copie admin impossible (doc %s)", doc.id)
        await db.rollback()
        raise HTTPException(status_code=500,
                            detail="La copie n'a pas pu être enregistrée.")
    nouveau.translated_path = copie
    await db.commit()
    logger.info("admin %s a copié le document %s (propriétaire %s) : copie %s",
                admin.email, doc.id, owner_email, nouveau.id)
    return {"id": nouveau.id, "cree": True}
