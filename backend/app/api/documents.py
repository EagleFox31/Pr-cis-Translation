"""
Routes documents — CRUD par utilisateur.
"""
from __future__ import annotations
import json
import os
import time
import unicodedata
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Response
from fastapi.responses import JSONResponse
from typing import Literal
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
# FileResponse retiré : ses réponses Range/206 faisaient échouer
# les fetch côté frontend (ERR_FAILED 206). On utilise Response partout.
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import TRANSLATIONS_DIR, logger
from app.services import beta, extension, images_document, ocr_pages, render_cache, stockage, translation_runner, usage
from app.services.beta_meter import BetaCost
from app.models.plans import get_plan_priority
from app.services.scheduler import scheduler_scans
from app.services.documents import copie_du_document as _copie_du_document, copie_prevue as _copie_prevue
from app.services.documents import acces_archive, acces_jusqu_au
from app.services.documents import (chemin_traduction_du_document, pages_selectionnees,
                                    reglages_de, traduction_partielle_du_document)
from app.services.jobs import STATUTS_ARRET, STATUTS_REPRENABLES, jobs
from app.services.office import convert_to_pdf_bytes
from app.services.translation_runner import render_translation_bytes
from app.core.database import get_db
from app.models import User, Document, is_paid_plan
from app.core.security import require_auth
from app.services.trial_preview import rasterize_for_trial


def _piece_jointe(nom: str) -> str:
    """En-tête Content-Disposition sûr pour tout nom de fichier.

    Un en-tête HTTP est encodé en latin-1 : un nom avec « — », de l'arabe ou du
    chinois y faisait échouer le téléchargement (500). Le nom exact passe par
    `filename*` (RFC 6266) ; `filename` garde un repli ASCII sans guillemets.
    """
    repli = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode()
    repli = repli.replace('"', "").replace("\\", "").strip() or "document"
    return f"attachment; filename=\"{repli}\"; filename*=UTF-8''{quote(nom, safe='')}"

router = APIRouter(prefix="/api/documents", tags=["Documents"])

# Le magasin est celui d'`app.py` : `backend/translations`. Cette constante
# valait `os.path.dirname(__file__)` — c'est-à-dire `backend/routes/` — et
# pointait donc sur `backend/routes/translations`, un dossier que la suppression
# créait à chaque appel et qui n'a jamais contenu un seul fichier (mesuré : 0
# ici contre 15 dans le vrai magasin). Le garde-fou de suppression « protégeait »
# les fichiers d'autrui en ne trouvant jamais rien à effacer : aucun octet n'a
# jamais été libéré, et `storage_used` dérivait du disque à chaque suppression.
#
# Le chemin n'est PLUS recalculé ici. Ce module avait sa propre expression,
# dérivée de son emplacement, et un simple déplacement de fichier suffisait à
# la faire diverger — c'est arrivé une deuxième fois lors de la réorganisation
# en paquets, et le test l'a rattrapé. Une seule définition, dans la config :
# la divergence devient impossible par construction, ce qui vaut mieux qu'un
# test qui la constate.
STORAGE_BASE = TRANSLATIONS_DIR


def _lire(chemin: str) -> bytes:
    """Lit un fichier ENTIER, à appeler par `run_in_threadpool`.

    Un `open().read()` dans un `async def` fige la boucle d'événements le temps
    de la lecture — donc TOUTE l'application, flux SSE de la traduction
    progressive compris. Le service ne tourne qu'avec un seul worker uvicorn
    (registre de jobs en mémoire) et les fichiers vont jusqu'à MAX_FILE_SIZE :
    un téléchargement de 100 Mo suspendait les aperçus de tous les autres.
    """
    # Windows : ouverture refusée pendant que le runner remplace le partiel.
    for essai in range(20):
        try:
            with open(chemin, "rb") as fh:
                return fh.read()
        except PermissionError:
            if essai == 19:
                raise
            time.sleep(0.05)


def _garder_pages(pdf: bytes, pages: set[int]) -> bytes:
    """Ne garde du PDF que les `pages` (numéros 1-basés), dans l'ordre."""
    import fitz
    with fitz.open(stream=pdf, filetype="pdf") as d:
        d.select([p - 1 for p in sorted(pages) if 0 < p <= len(d)])
        return d.tobytes(garbage=3, deflate=True)


def _sans_pages_retirees(pdf: bytes, trad: str) -> bytes:
    """Retire du fichier livré les pages hors sélection que le client a
    retirées ; l'aperçu, lui, les garde à leur place."""
    retirees = ocr_pages.pages_retirees(trad)
    if not retirees:
        return pdf
    import fitz
    with fitz.open(stream=pdf, filetype="pdf") as d:
        total = len(d)
    return _garder_pages(pdf, set(range(1, total + 1)) - retirees)


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


def _job_root(path: str) -> str | None:
    """Racine du job dans le magasin : `translations/{nom}_{hash}`.

    C'est l'unité de PROPRIÉTÉ partagée : tout ce qu'un job produit (original,
    extractions, rendus par version de moteur) vit sous ce dossier. None si le
    chemin n'est pas strictement SOUS le magasin.
    """
    real = os.path.realpath(path)
    store = os.path.realpath(STORAGE_BASE)
    try:
        rel = os.path.relpath(real, store)
    except ValueError:                    # autre volume (Windows)
        return None
    premier = rel.split(os.sep)[0]
    if premier in ("..", ".", ""):
        return None
    return os.path.join(store, premier)


async def _purge_if_orphan(db: AsyncSession, path: str) -> bool:
    """Efface `path` SI plus aucun Document, de quelque compte que ce soit, ne
    référence LE JOB auquel il appartient.

    Les fichiers vivent dans un magasin PARTAGÉ adressé par le hash du contenu :
    deux comptes ayant déposé le même fichier pointent sur les mêmes octets.
    Effacer sur la seule foi de « mon » Document supprimerait la traduction
    d'autrui. On compte donc les références restantes — la ligne courante est
    déjà supprimée ET commitée, elle ne se compte pas elle-même.

    Le comptage se fait sur la RACINE du job, pas sur le chemin exact : le
    `translated_path` d'un Document reste NULL pendant toute la traduction, et
    un comptage au fichier près déclarait donc orphelin un rendu qu'un autre
    compte était en train de produire. Tant qu'UNE référence pointe quelque
    part sous la racine (ne serait-ce que l'original), rien n'y est effacé —
    conservateur, mais de la rétention de disque plutôt que la perte du
    fichier d'autrui.
    """
    if await _racine_orpheline(db, path) is None:
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


async def _racine_orpheline(db: AsyncSession, path: str) -> str | None:
    """Racine du job de `path` si plus AUCUN Document n'y renvoie, sinon None."""
    if not _inside_store(path):
        return None
    racine = _job_root(path)
    if racine is None:
        return None
    prefixe = racine + os.sep
    refs = await db.execute(
        select(func.count()).select_from(Document).where(
            or_(
                Document.original_path == racine,
                Document.translated_path == racine,
                Document.original_path.startswith(prefixe, autoescape=True),
                Document.translated_path.startswith(prefixe, autoescape=True),
            ),
        )
    )
    if (refs.scalar() or 0) > 0:
        return None                       # quelqu'un d'autre tient encore au job
    return racine


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


def _render_or_404(doc: Document, ext: str,
                   only_pages: set[int] | None = None,
                   trad: str | None = None) -> bytes:
    """Recalcule le document traduit depuis l'original + la traduction stockée.

    Le rendu est un SERVICE (`app.services.translation_runner`), pas
    l'application. Cette fonction faisait auparavant `import app` en paresseux
    pour contourner le cycle que creait `include_router` ; la fabrique
    `create_app()` ayant supprime le cycle, l'import est redevenu normal.

    `trad` : la traduction à rendre, `doc.translated_path` par défaut (une
    traduction partielle pour un document arrêté, voir `_traduction`).
    `only_pages` borne alors les pages traduites livrées ; la sélection du
    job numérote les diapositives d'une traduction PPTX finale.
    """
    trad = trad or doc.translated_path
    if (not doc.original_path or not os.path.isfile(doc.original_path)
            or not trad or not os.path.isfile(trad)):
        raise HTTPException(status_code=404,
                            detail="Le fichier n'est plus disponible. Réessayez ou rechargez la page.")
    selection = {int(p) for p in str(reglages_de(doc).get("pages") or "").split(",")
                 if p.strip().isdigit()}
    try:
        return render_translation_bytes(
            doc.original_path, trad, ext, doc.target_lang,
            only_pages=only_pages, selection=selection or None)
    except Exception:
        logger.exception("Rendu impossible (doc %s, %s)", getattr(doc, "id", "?"), ext)
        raise HTTPException(status_code=500,
                            detail="Le rendu du document a échoué. Réessayez dans quelques instants.")


async def _traduction(db: AsyncSession, doc: Document) -> tuple[str | None, set[int] | None]:
    """(traduction à livrer, pages livrables : None si elle est complète).

    Un document arrêté avant la fin (interrompu, en pause, annulé) n'a pas de
    `translated_path` mais ses pages traduites sont payées : il les reçoit, au
    plus autant qu'il en a payé, le reste en langue d'origine. Ce rendu
    partiel n'est jamais mis en cache : le cache est indexé par le fichier,
    partagé entre comptes, et un autre document y prendrait d'autres pages."""
    if doc.translated_path:
        return doc.translated_path, None
    if doc.status not in STATUTS_REPRENABLES:
        return None, None
    payees = (await usage.pages_payees(db, doc.id)
              + int(reglages_de(doc).get("deja") or 0))
    partielle = await run_in_threadpool(traduction_partielle_du_document, doc, payees)
    return partielle or (None, None)


def _exiger_acces(user: User, doc: Document) -> None:
    """403 `stockage_requis` sur un document archivé (forfait sans stockage,
    plus de 30 jours) : il reste listé et supprimable, plus ouvrable."""
    if acces_archive(user, doc):
        raise HTTPException(status_code=403, detail="stockage_requis")


def _may_read_clear(user: User, doc: Document) -> bool:
    """A-t-on le droit de voir CE document en clair (et de le télécharger) ?

    Deux titres différents, et il suffit d'en avoir un :
      • l'abonnement — un plan payant couvre tout ce qu'il produit ;
      • l'achat — le forfait Gratuit paie à la page, et ce qu'il a payé lui
        appartient au même titre.

    Le droit était lu sur le seul PLAN. C'était juste tant que le gratuit ne
    pouvait rien acheter ; ça devient faux dès qu'il le peut — il aurait payé
    des pages sans jamais pouvoir les récupérer.
    """
    return is_paid_plan(user.plan) or doc.paid


def _apercu_filigrane(user: User, doc: Document) -> bool:
    """L'aperçu de CE document porte-t-il la mention promotionnelle ?

    Oui sans droit au clair, et aussi pour un document traduit avec des crédits
    bêta : téléchargeable, mais son aperçu reste filigrané, même sur un compte
    payant (conditions d'utilisation, « Offres et quotas »)."""
    return not _may_read_clear(user, doc) or bool(reglages_de(doc).get("beta"))


def _suivi_scan(doc: Document) -> dict:
    """Pages illisibles d'un scan terminé : celles qui attendent un choix,
    et celles en cours de relecture (« traduire quand même »)."""
    trad = doc.translated_path
    if doc.status == "translating" or not trad or not os.path.isfile(trad):
        return {"pages_a_decider": 0, "pages_relues": 0}
    illisibles = ocr_pages.pages_illisibles(trad)
    if not illisibles:
        return {"pages_a_decider": 0, "pages_relues": 0}
    en_cours = translation_runner.pages_en_cours(trad) & set(illisibles)
    choix = ocr_pages.lire_choix(trad)
    return {"pages_a_decider": sum(1 for p in illisibles if p not in choix and p not in en_cours),
            "pages_relues": len(en_cours)}


def _doc_response(doc: Document, user: User) -> dict:
    fin = acces_jusqu_au(user, doc)
    return {
        **_suivi_scan(doc),
        "id": doc.id,
        "paid": doc.paid,
        "original_name": doc.original_name,
        "source_lang": doc.source_lang,
        "target_lang": doc.target_lang,
        "size_bytes": doc.size_bytes,
        "status": doc.status,
        "page_count": doc.page_count,
        "pages_done": doc.pages_done,
        "reglages": json.loads(doc.reglages) if doc.reglages else None,
        # Pause / Annuler depuis la bibliothèque. Le propriétaire est revérifié
        # par la route d'arrêt : la liste ne fait que nommer le job.
        "job_id": jobs.id_for_document(doc.id) if doc.status == "translating" else None,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        "archive": acces_archive(user, doc),
        "acces_jusqu_au": fin.isoformat() if fin else None,
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
    # Lit les pages illisibles sur disque : hors de la boucle.
    return await run_in_threadpool(lambda: [_doc_response(d, user) for d in docs])


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
    return _doc_response(doc, user)


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
    _exiger_acces(user, doc)

    trad, livrables = await _traduction(db, doc)
    # Liste d'AUTORISATION : un plan inconnu est traité comme non payant.
    if trad and not _may_read_clear(user, doc):
        raise HTTPException(
            status_code=402,
            detail="Cette traduction n'est pas payée. Réglez ses pages pour "
                   "la télécharger, ou passez à Starter.",
        )

    ext = os.path.splitext(doc.original_name)[1].lstrip(".").lower()

    # Pas encore de traduction : on rend l'original (le fichier de l'utilisateur).
    if not trad:
        if not doc.original_path or not os.path.isfile(doc.original_path):
            raise HTTPException(status_code=404, detail="Le fichier n'est plus disponible. Réessayez ou rechargez la page.")
        data = await run_in_threadpool(_lire, doc.original_path)
        return Response(content=data, media_type="application/octet-stream",
                        headers={"Content-Disposition": _piece_jointe(doc.original_name)})

    # `translated_path` désigne la TRADUCTION stockée (JSON), pas un rendu.
    #
    # Le cache de rendu ne contient QUE des PDF (c'est un cache d'APERÇU, cf.
    # render_cache.py). Pour un PDF, ce rendu EST le fichier téléchargeable —
    # on le réutilise. Pour tout autre format (PPTX, DOCX), le cache tient une
    # CONVERSION PDF de l'aperçu, PAS le document natif : le servir ici rendait
    # un PDF déguisé en .pptx que PowerPoint refusait d'ouvrir. On ne touche
    # donc au cache que pour le PDF ; les autres formats se régénèrent toujours
    # dans leur format natif.
    #
    # Reconstruire 285 pages dans la requête prenait 280 s (téléchargement qui
    # expire) : on reconstruit dans un thread (la boucle d'événements ne se fige
    # pas) et, pour le PDF, on CONSERVE le résultat — la lenteur ne se paie
    # qu'une fois.
    def _build() -> bytes:
        if livrables is not None:       # partiel : jamais le cache, voir `_traduction`
            data = _render_or_404(doc, ext, only_pages=livrables, trad=trad)
            # Le TÉLÉCHARGEMENT d'un arrêt ne livre que les pages traduites :
            # les autres, recopiées de l'original pour l'aperçu côte à côte,
            # ne sont pas la traduction que le client a payée.
            return _garder_pages(data, livrables) if ext == "pdf" else data
        if ext == "pdf":
            cached = render_cache.cache_valid(trad)
            if cached:
                with open(cached, "rb") as f:
                    return f.read()
            marque, avant = render_cache.marque_polices(), render_cache.mtime_de(trad)
            data = _render_or_404(doc, ext, trad=trad)
            render_cache.store_render(data, trad, marque, avant)
            return data
        # Format natif non-PDF : jamais le cache d'aperçu.
        return _render_or_404(doc, ext, trad=trad)

    data = await run_in_threadpool(_build)
    if ext == "pdf" and livrables is None:
        data = await run_in_threadpool(_sans_pages_retirees, data, trad)
    base = os.path.splitext(doc.original_name)[0]
    dl_name = f"{base}_TRADUIT{'_PARTIEL' if livrables is not None else ''}.{ext}"
    media = "application/pdf" if ext == "pdf" else "application/octet-stream"
    return Response(content=data, media_type=media,
                    headers={"Content-Disposition": _piece_jointe(dl_name)})


# ── GET /documents/{id}/original ─────────────────────────────────────────────

@router.get("/{doc_id}/original")
async def original_document(
    doc_id: str,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
    # EN DERNIER, comme `page` sur /preview : un paramètre inséré avant `user`
    # décalerait les appels POSITIONNELS existants (dont les tests).
    as_: str | None = Query(None, alias="as"),
):
    """Le fichier SOURCE, tel qu'il a été déposé — ou converti en PDF.

    /download rend la TRADUCTION dès qu'elle existe : impossible d'y récupérer
    la source. L'aperçu depuis la bibliothèque n'avait donc rien à afficher dans
    son panneau de gauche et retombait sur le PDF de DÉMO — on montrait le
    journal d'exemple à côté du CV de l'utilisateur.

    `?as=pdf` — POUR REGARDER, PAS POUR REPARTIR AVEC.
    Le viewer affiche tout en PDF. Sans ce paramètre, le client téléchargeait le
    PPTX natif (13,4 Mo mesurés sur un deck de 26 slides) puis le RENVOYAIT au
    serveur en multipart sur /api/preview/pdf pour que celui-ci le convertisse —
    alors que le serveur détient déjà cette conversion en cache (2,5 Mo). Trois
    transferts et une conversion pour un fichier qu'il suffisait de servir : le
    panneau gauche restait blanc dès que ce détour échouait, sans rien dire.
    La conversion est mise en cache par CONTENU (cf. convert_to_pdf_bytes) : le
    coût n'est payé qu'une fois pour tous les utilisateurs du même fichier.

    SANS `as`, on rend toujours les octets d'origine : c'est ce dont dépend la
    relance d'une traduction, qui a besoin du fichier NATIF.

    Aucun contrôle de plan : c'est le fichier de l'utilisateur.
    """
    doc = await db.get(Document, doc_id)
    if doc is None or doc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    _exiger_acces(user, doc)
    if not doc.original_path or not os.path.isfile(doc.original_path):
        raise HTTPException(status_code=404, detail="Le fichier n'est plus disponible. Réessayez ou rechargez la page.")
    # Response explicite plutôt que FileResponse : évite les Range/206 qui
    # peuvent faire échouer le fetch côté frontend (ERR_FAILED 206).
    data = await run_in_threadpool(_lire, doc.original_path)
    ext = os.path.splitext(doc.original_name)[1].lstrip(".").lower()

    if as_ == "pdf" and ext != "pdf":
        try:
            data = await run_in_threadpool(convert_to_pdf_bytes, data, ext)
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="La conversion du document source pour l'aperçu a échoué.")
        ext = "pdf"

    media = "application/pdf" if ext == "pdf" else "application/octet-stream"
    return Response(content=data, media_type=media)


# ── GET /documents/{id}/preview ──────────────────────────────────────────────

def _entetes_pages(job: dict | None) -> dict[str, str]:
    """Où en est chaque page d'un document EN COURS. Rouvert depuis la
    bibliothèque, l'aperçu n'a pas le flux de la traduction : sans ces
    en-têtes, il tenait toutes les pages pour traduites (vertes, et le texte
    d'origine affiché à la place de la traduction)."""
    if not job:
        return {"X-Pages-Pretes": "", "X-Pages-Etats": ""}
    pretes, etats = jobs.pages_etat(job)
    return {
        "X-Pages-Pretes": ",".join(map(str, pretes)),
        "X-Pages-Etats": ",".join(f"{p}:{s}" for p, s in sorted(etats.items())),
    }


@router.get("/{doc_id}/preview")
async def preview_document(
    doc_id: str,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
    # EN DERNIER, volontairement. Inséré après `doc_id`, ce paramètre décalait
    # tous les appels POSITIONNELS existants : `preview_document(id, user, db)`
    # passait `user` pour `page`, et `db` restait un `Depends` non résolu. Un
    # nouvel argument optionnel se met à la fin — la suite de tests l'a montré
    # avant que ça n'atteigne quiconque.
    page: int | None = None,
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
    _exiger_acces(user, doc)

    ext = os.path.splitext(doc.original_name)[1].lstrip(".").lower()

    # Pas encore de traduction consignée : le document est EN COURS (la
    # bibliothèque laisse « Aperçu » actif pendant la traduction). On renvoyait
    # l'original à la place de la traduction : rouvert depuis la liste, l'aperçu
    # montrait original/original et n'avançait plus. On sert désormais le PDF
    # PARTIEL du job (les pages déjà traduites), ou « rien encore » — jamais
    # l'original déguisé en traduction. `X-Render` dit au client de redemander.
    trad, livrables = await _traduction(db, doc)
    if not trad:
        job = jobs.for_document(doc.id)
        etat = job.get("state") if job else None
        # Job FINI mais base pas à jour (report `sync_status` échoué) : servir
        # le partiel ici ferait redemander le client indéfiniment. Le rendu
        # final du job, s'il existe, est la vraie réponse ; sinon, rien.
        # Hors PDF, le rendu final n'est pas un PDF : on garde le partiel
        # (déjà converti) le temps que `sync_status` consigne la traduction —
        # une minute au plus, sinon un report échoué ferait redemander le
        # client sans fin.
        if etat == "done" and job.get("result_path") and ext == "pdf":
            chemin, rendu = job["result_path"], "full"
        elif etat == "done" and time.time() - job.get("finished_at", 0) < 60:
            chemin, rendu = job.get("partial_path"), "partial"
        elif etat in ("done", "error", *STATUTS_ARRET) or doc.status != "translating":
            chemin, rendu = None, None
        else:
            chemin, rendu = job.get("partial_path") if job else None, "partial"
        if not chemin or not os.path.isfile(chemin):
            if rendu != "partial":
                raise HTTPException(status_code=404, detail="Traduction indisponible. Relancez-la depuis la bibliothèque.")
            return Response(status_code=202, headers={"Cache-Control": "no-store",
                                                      "X-Render": "pending",
                                                      **_entetes_pages(job)})
        data = await run_in_threadpool(_lire, chemin)
        if _apercu_filigrane(user, doc):
            # Même règle que /translate/partial : un plan d'essai ne reçoit
            # que des pixels, et seules les pages traduites sont à protéger.
            data = await run_in_threadpool(rasterize_for_trial, data, job.get("pages"))
        entetes = _entetes_pages(job) if rendu == "partial" else {}
        return Response(content=data, media_type="application/pdf",
                        headers={"Cache-Control": "no-store",
                                 "X-Render": rendu, **entetes})

    # Un plan d'essai ne reçoit que du rastérisé, et seulement pour le PDF : un
    # format non-PDF ne peut pas être filigrané ici sans risque de le livrer en
    # clair, donc on le réserve aux plans payants.
    clear = not _apercu_filigrane(user, doc)
    if not _may_read_clear(user, doc) and ext != "pdf":
        raise HTTPException(
            status_code=402,
            detail="Aperçu de ce format réservé aux traductions payées.",
        )

    # Rendu + rastérisation sont du CPU pur, de l'ordre de la seconde par page.
    # Exécutés dans la coroutine, ils bloquaient la boucle d'événements : cliquer
    # « Aperçu » figeait TOUTE l'application jusqu'à la fin du rendu. On les
    # sort dans un thread, et on n'en fait qu'un aller-retour (les deux étapes
    # sont enchaînées côté thread plutôt qu'en deux bascules).

    # ── Rendre UNE page n'a de sens que pour le PDF ───────────────────────
    #
    # Le moteur v2 sait ne reconstruire qu'une page et recopier les autres de
    # l'original : demander `?page=N` y économise vraiment (280 s le document de
    # 285 pages, ~8 s la page seule).
    #
    # Un PPTX ou un DOCX, lui, se réinjecte D'UN BLOC puis passe en entier par
    # LibreOffice : `only_pages` n'y change rien, la page demandée coûte le
    # document entier. Or on jetait ce rendu au motif qu'une page avait été
    # demandée (`if clear and not fenetre`) — et le frontend envoie TOUJOURS
    # `?page=N`. Le cache n'était donc jamais écrit, `X-Render: full` jamais
    # émis : chaque changement de page repayait la réinjection complète plus une
    # conversion LibreOffice. On paie ce rendu une fois, on le garde, et le
    # client reçoit tout le document d'un coup.
    fenetre = {page} if (page and page > 0 and ext == "pdf") else None

    # ── Chemin RAPIDE : le rendu complet est en cache ─────────────────────
    #
    # Une fois servi, le client a TOUT le document traduit (converti en PDF) :
    # plus une seule requête pendant la navigation (l'en-tête `X-Render: full`
    # le lui dit). Réservé au CLAIR : la version d'essai est rastérisée à la
    # demande, et rastériser 285 pages par requête coûterait plus que ce qu'on
    # évite.
    if clear and livrables is None:
        cached = render_cache.cache_valid(trad)
        if cached:
            data = await run_in_threadpool(_lire, cached)
            return Response(content=data, media_type="application/pdf",
                            headers={"Cache-Control": "no-store",
                                     "X-Render": "full"})

    def _build_complet() -> bytes:
        """Rendu INTÉGRAL, en PDF, CONSERVÉ. Un seul à la fois par document.

        Le verrou n'est pas une précaution de style : sans lui, deux requêtes
        d'aperçu simultanées construisaient le même rendu en parallèle — deux
        réinjections PPTX dans deux moteurs, deux conversions LibreOffice, pour
        un seul résultat. Le second entrant retrouve ici le cache déjà écrit.
        Un partiel, lui, n'est ni lu ni écrit dans le cache (voir `_traduction`).
        """
        if livrables is not None:
            data = _render_or_404(doc, ext, only_pages=livrables, trad=trad)
            return convert_to_pdf_bytes(data, ext) if ext != "pdf" else data
        with render_cache.build_lock(trad):
            cached = render_cache.cache_valid(trad)
            if cached:
                with open(cached, "rb") as f:
                    return f.read()
            marque, avant = render_cache.marque_polices(), render_cache.mtime_de(trad)
            data = _render_or_404(doc, ext, only_pages=None, trad=trad)
            if ext != "pdf":
                data = convert_to_pdf_bytes(data, ext)
            render_cache.store_render(data, trad, marque, avant)
            return data

    if fenetre is None:
        data = await run_in_threadpool(_build_complet)
        if not clear:
            data = await run_in_threadpool(rasterize_for_trial, data)
        return Response(content=data, media_type="application/pdf",
                        headers={"Cache-Control": "no-store",
                                 "X-Render": "full"})

    # ── PDF, page par page ────────────────────────────────────────────────
    # Les pages non rendues sont recopiées de l'original, donc la pagination
    # reste celle du document — le lecteur n'a rien à recalculer. En tâche de
    # fond, on construit UNE fois le rendu complet : quelques minutes plus tard,
    # la navigation est instantanée et ne redemande plus rien.
    if clear and livrables is None:
        render_cache.ensure_background_build(
            doc.original_path, trad, ext, doc.target_lang)
    if livrables is not None:
        fenetre &= livrables        # page non payée : celle de l'original

    def _build_page() -> bytes:
        data = _render_or_404(doc, ext, only_pages=fenetre, trad=trad)
        if not clear:
            data = rasterize_for_trial(data)      # ext == "pdf" garanti ici
        return data

    data = await run_in_threadpool(_build_page)
    return Response(content=data, media_type="application/pdf",
                    headers={"Cache-Control": "no-store",
                             "X-Render": "page"})


# ── DELETE /documents/{id} ───────────────────────────────────────────────────

# ── Images traduites : remettre l'original (étude images-documents §8) ───────

class ChoixImage(BaseModel):
    cle: str = Field(min_length=1, max_length=512)
    originale: bool


async def _doc_traduit(db: AsyncSession, user: User, doc_id: str) -> Document:
    doc = await db.get(Document, doc_id)
    if doc is None or doc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    _exiger_acces(user, doc)
    if not doc.translated_path or not os.path.isfile(doc.translated_path):
        raise HTTPException(status_code=404, detail="Ce document n'a pas de traduction disponible.")
    return doc


def _images_du_document(doc: Document) -> list[dict]:
    etat = images_document.etat_images(doc.translated_path)
    if not etat:
        return []
    ext = os.path.splitext(doc.original_name)[1].lstrip(".").lower()
    originales: dict[str, images_document.ImageDoc] = {}
    try:
        with open(doc.original_path, "rb") as f:
            originales = {i.cle: i for i in images_document.lister(f.read(), ext)}
    except (OSError, ValueError, TypeError):
        pass

    def vignette(octets: bytes | None) -> str | None:
        try:
            return images_document.vignette(octets) if octets else None
        except Exception:
            return None

    sortie = []
    for cle, originale, octets in etat:
        source = originales.get(cle)
        sortie.append({
            "cle": cle,
            "originale": originale,
            "pages": source.pages if source else [],
            "vignette_traduite": vignette(octets),
            "vignette_originale": vignette(source.octets if source else None),
        })
    return sortie


def _invalider_rendu(trad: str) -> None:
    render_cache.invalider(trad)


@router.get("/{doc_id}/images")
async def images_traduites(
    doc_id: str,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Images traduites du document, avec leur état (original ou traduite)."""
    doc = await _doc_traduit(db, user, doc_id)
    return {"images": await run_in_threadpool(_images_du_document, doc)}


@router.patch("/{doc_id}/images")
async def choisir_image(
    doc_id: str,
    choix: ChoixImage,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Remet une image à l'original, ou rétablit sa traduction. Aucun
    remboursement : l'image traduite reste gardée pour revenir en arrière."""
    doc = await _doc_traduit(db, user, doc_id)
    if not any(cle == choix.cle for cle, _, _ in
               await run_in_threadpool(images_document.etat_images, doc.translated_path)):
        raise HTTPException(status_code=404, detail="Image introuvable dans ce document.")
    try:
        copie = await run_in_threadpool(_copie_du_document, doc)
    except OSError:
        logger.exception("Copie de traduction impossible (doc %s)", doc.id)
        raise HTTPException(status_code=500, detail="Le changement n'a pas pu être enregistré.")
    if copie != doc.translated_path:
        doc.translated_path = copie
        await db.commit()
    await run_in_threadpool(images_document.marquer_originale, copie, choix.cle, choix.originale)
    await run_in_threadpool(_invalider_rendu, copie)
    return {"cle": choix.cle, "originale": choix.originale}


# ── Pages illisibles d'un scan : original, vide ou traduire quand même ───────

class ChoixPages(BaseModel):
    pages: list[int] = Field(min_length=1, max_length=2000)
    choix: Literal["original", "vide", "traduire", "retirer"]


def _hors_selection(doc: Document, trad: str) -> set[int]:
    """Pages d'un PDF laissées hors de la sélection du job et pas encore
    incluses. Une traduction d'avant `selection.json` la retrouve dans les
    réglages du document (son rendu, posé sans mention, est alors refait)."""
    if not doc.original_path or not doc.original_path.lower().endswith(".pdf"):
        return set()
    if ocr_pages.lire_selection(trad) is None:
        selection = pages_selectionnees(doc)
        if not selection:
            return set()
        ocr_pages.ecrire_selection(trad, selection)
        _invalider_rendu(trad)
    import fitz
    try:
        with fitz.open(doc.original_path) as d:
            total = d.page_count
        with render_cache.verrou_traduction(trad).lire():
            with open(trad, encoding="utf-8") as f:
                presentes = {p.get("page_num") for p in json.load(f).get("pages", [])}
    except (OSError, ValueError, RuntimeError):
        return set()
    return ocr_pages.pages_hors_selection(trad, total, presentes)


def _pages_illisibles_du_document(doc: Document, trad: str | None = None) -> dict:
    """`provisoire` : traduction encore en cours, les pages se lisent au fil
    du scan mais aucun choix n'est encore possible (il porte sur la copie
    du document, posée à la fin). Les pages hors sélection (motif
    `hors_selection`) n'apparaissent qu'une fois la traduction terminée."""
    provisoire = trad is not None and trad != doc.translated_path
    trad = trad or doc.translated_path
    choix = {} if provisoire else ocr_pages.lire_choix(trad)
    entrees = dict(ocr_pages.pages_illisibles(trad))
    if not provisoire:
        entrees.update({p: "hors_selection" for p in _hors_selection(doc, trad)})
    return {
        "pages": [{"page": page, "motif": motif, "choix": choix.get(page)}
                  for page, motif in sorted(entrees.items())],
        "en_cours": [] if provisoire else sorted(translation_runner.pages_en_cours(trad)),
        "provisoire": provisoire,
        # Vignettes : une page blanche n'est ni traduite ni à décider.
        "blanches": ocr_pages.pages_blanches(trad),
    }


@router.get("/{doc_id}/pages-illisibles")
async def pages_illisibles(
    doc_id: str,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Pages d'un scan restées illisibles, avec le choix du client pour chacune.
    Pendant la traduction, celles déjà lues (sans choix possible)."""
    doc = await db.get(Document, doc_id)
    if doc is None or doc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    if doc.translated_path and os.path.isfile(doc.translated_path):
        return await run_in_threadpool(_pages_illisibles_du_document, doc)
    prevu = (await run_in_threadpool(chemin_traduction_du_document, doc)
             if doc.status in ("pending", "translating") else None)
    if not prevu:
        raise HTTPException(status_code=404, detail="Ce document n'a pas de traduction disponible.")
    return await run_in_threadpool(_pages_illisibles_du_document, doc, prevu)


async def _couvre_les_pages(db: AsyncSession, user: User, doc: Document, n: int) -> JSONResponse | None:
    """402 si ni le forfait, ni le solde (ou le quota bêta) ne couvrent `n` pages."""
    if reglages_de(doc).get("beta"):
        inscription = await beta.active_enrollment(db, user)
        try:
            if inscription is None:
                raise HTTPException(402, {"reason": "beta_quota", "message":
                                          "Votre accès bêta n'est plus actif."})
            await beta.check_cost(db, inscription, BetaCost("pdf", n))
        except HTTPException as exc:
            return JSONResponse(status_code=402, content={**exc.detail, "detail": exc.detail["message"]})
        return None
    reste_plan, solde, _ = await extension.couverture(db, user)
    if extension.couvre(reste_plan, solde, n):
        return None
    message = "Votre solde ne couvre pas ces pages. Rechargez vos crédits pour les traduire."
    return JSONResponse(status_code=402, content={
        "reason": "insufficient_credits", "required": n, "detail": message, "message": message})


@router.patch("/{doc_id}/pages-illisibles")
async def choisir_pages_illisibles(
    doc_id: str,
    corps: ChoixPages,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """« original » ou « vide » change le rendu, sans débit. « traduire » relit
    les pages plus permissivement ; seule une page traduite est débitée."""
    doc = await _doc_traduit(db, user, doc_id)
    pages = sorted(set(corps.pages))
    illisibles = await run_in_threadpool(ocr_pages.pages_illisibles, doc.translated_path)
    hors = await run_in_threadpool(_hors_selection, doc, doc.translated_path)
    if any(p not in illisibles and p not in hors for p in pages):
        raise HTTPException(status_code=409, detail="Ces pages ne sont plus à décider.")
    # « vide » ne vaut que pour une page illisible, « retirer » que pour une
    # page hors sélection.
    if ((corps.choix == "vide" and any(p in hors for p in pages))
            or (corps.choix == "retirer" and any(p in illisibles for p in pages))):
        raise HTTPException(status_code=409, detail="Ce choix ne convient pas à ces pages.")
    if corps.choix == "traduire":
        # Les pages en cours sont marquées sur la copie propre au document.
        cible = _copie_prevue(doc)
        pages = [p for p in pages if p not in translation_runner.pages_en_cours(cible)]
        if not pages:
            return await run_in_threadpool(_pages_illisibles_du_document, doc)
        refus = await _couvre_les_pages(db, user, doc, len(pages))
        if refus is not None:
            return refus
    try:
        copie = await run_in_threadpool(_copie_du_document, doc)
    except OSError:
        logger.exception("Copie de traduction impossible (doc %s)", doc.id)
        raise HTTPException(status_code=500, detail="Le changement n'a pas pu être enregistré.")
    if copie != doc.translated_path:
        doc.translated_path = copie
        await db.commit()
    if corps.choix != "traduire":
        # « original » est un choix enregistré comme « vide » : sans trace,
        # la page reste « à décider » et la carte revient.
        await run_in_threadpool(ocr_pages.ecrire_choix, copie, pages, corps.choix)
        await run_in_threadpool(_invalider_rendu, copie)
        return await run_in_threadpool(_pages_illisibles_du_document, doc)
    nouvelles = translation_runner.reserver_pages(copie, pages)
    if nouvelles:
        job_id = jobs.create()
        try:
            scheduler_scans.submit(job_id, get_plan_priority(user.plan),
                                   translation_runner.run_traduire_pages_job,
                                   (job_id, doc.id, user.id, doc.original_path, copie,
                                    doc.target_lang, sorted(nouvelles),
                                    bool(reglages_de(doc).get("beta"))))
        except Exception:
            translation_runner.liberer_pages(copie, nouvelles)
            jobs.forget(job_id)
            raise
    return await run_in_threadpool(_pages_illisibles_du_document, doc)


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

    # On rembourse ce qui a été FACTURÉ, pas la taille du fichier. Un dépôt à
    # quota plein (ou sur plan sans stockage) est facturé 0 : rembourser `size`
    # faisait descendre `storage_used` sous la réalité à chaque suppression.
    charge = doc.storage_charged or 0
    original_path = doc.original_path
    await db.delete(doc)

    # Libérer le quota
    user.storage_used = max(0, user.storage_used - charge)
    await db.commit()

    # Purge par comptage de références. Le commit ci-dessus est INDISPENSABLE
    # avant de compter : tant que la suppression n'est pas validée, la ligne
    # courante se compterait elle-même et rien ne serait jamais orphelin.
    #
    # C'est TOUT le dossier du job qui part, pas les deux seuls chemins connus
    # de la base : rendus en cache, extractions, autres plages et sorties de
    # job restaient sinon sur le disque pour toujours (mesuré : 70 Mo sur 90).
    purged = 0
    racine = await _racine_orpheline(db, original_path)
    if racine and stockage.purger_racine(racine):
        purged = 1

    return {"message": "Document supprimé.", "storage_freed": charge,
            "files_purged": purged}
