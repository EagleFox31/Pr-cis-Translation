"""Routes de traduction : depot, suivi SSE, partiel, resultat, apercu.

Ces routes ne traduisent pas elles-memes. Elles valident la demande, verifient
les droits, ouvrent un job et confient le travail a un THREAD worker
(`app.services.translation_runner`). Tout ce qui bloque -- reseau, LibreOffice,
rendu -- doit rester hors de la boucle asyncio, sinon c'est toute
l'application, flux SSE compris, qui se fige.
"""
from __future__ import annotations

import asyncio
import json
import os
import queue
from typing import Literal

from fastapi import (APIRouter, Depends, File, Form, Header, HTTPException,
                     Request, UploadFile)
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.documents import _may_read_clear
from app.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE, logger, resolve_quality
from app.core.database import get_db
from app.core.files import (get_file_hash, pages_token, parse_page_range,
                            sanitize_filename)
from app.core.security import require_auth, verify_access_token
from app.models import (Document, User, get_plan_page_limit,
                        get_plan_priority, get_plan_storage,
                        get_plan_monthly_pages, is_paid_plan,
                        KIND_CREDITS, KIND_FREE_OFFER, KIND_PLAN)
from app.rate_limit import verify_api_key
from app.services.documents import (build_job_paths, cap_pages_for_plan,
                                    count_pages, pages_avec_texte, pages_faites,
                                    reglages_de, translation_path_for)
from app.services import usage
from app.services import anti_abus
from app.services import beta
from app.services.beta_meter import BetaCost, FORMATS as BETA_FORMATS, office_cost
from app.services.ocr import OCR_VERSION, OCRError, prepare_scanned_pdf
from app.services.jobs import STATUTS_ARRET, STATUTS_REPRENABLES, jobs
from app.services.office import convert_to_pdf_bytes
from app.services.scheduler import scheduler
from app.services.translation_runner import (run_pdf_v2_job,
                                             run_pptx_progressive_job,
                                             run_translation_job,
                                             run_xlsx_progressive_job,
                                             _sauver_original)
from app.services.trial_preview import rasterize_for_trial

router = APIRouter(tags=["Traduction"])


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.options("/api/translate")
async def translate_options():
    return JSONResponse(content={}, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-API-Key",
    })

@router.options("/api/preview/pdf")
async def preview_pdf_options():
    return JSONResponse(content={}, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-API-Key",
    })

@router.post("/api/preview/pdf")
async def preview_pdf_endpoint(
    request: Request,
    file: UploadFile = File(...),
    x_api_key: str = Header(None),
    # CONNEXION OBLIGATOIRE : la clé d'API est publique (bundle du frontend),
    # elle ne « protège » rien. Sans JWT, cet endpoint était une ferme de
    # conversion LibreOffice ouverte à n'importe qui sur Internet.
    current_user: "User" = Depends(require_auth),
):
    """Convertit un document (DOCX/PPTX/TXT) en PDF pour l'aperçu côté client.
    Les PDF sont renvoyés tels quels. La conversion ne change pas le fichier
    téléchargeable, elle ne sert qu'à un rendu exact dans le viewer."""
    verify_api_key(x_api_key)

    filename = file.filename or ""
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Type non supporté pour l'aperçu : .{ext}")

    try:
        file_bytes = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Impossible de lire le fichier. Vérifiez qu'il n'est pas corrompu et réessayez.")

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Fichier trop volumineux pour l'aperçu.")

    try:
        pdf_bytes = await asyncio.to_thread(convert_to_pdf_bytes, file_bytes, ext)
    except Exception as e:
        logger.error(f"Conversion aperçu PDF échouée : {e}")
        raise HTTPException(status_code=500, detail="La conversion du PDF a échoué. Vérifiez que le fichier est un PDF valide et non corrompu.")

    return Response(content=pdf_bytes, media_type="application/pdf")


async def _save_document_for_user(user: "User | None", db: "AsyncSession",
                                  job_id: str, filename: str, target_lang: str,
                                  original_path: str, size: int,
                                  paid: bool = False, page_count: int = 1,
                                  usages: list[tuple[str, int]] = (), beta_charge=None,
                                  reglages: dict | None = None):
    """Enregistre un Document pour l'utilisateur connecté.

    La consommation (`usages` : une ligne par titre — quota du plan, pages
    achetées, offre du mois) est consignée dans `usage_records`, dans la
    MÊME transaction : c'est elle que comptent les quotas, et elle survit à la
    suppression du document. Le stockage n'est facturé que si le plan en offre
    ET que le quota le permet ; sinon `charge = 0`.

    Un échec ici LÈVE : le débit du solde de pages est dans cette transaction,
    l'avaler laissait partir une traduction ni enregistrée ni payée."""
    if user is None:
        return
    try:
        plan_storage = get_plan_storage(user.plan)
        charge = size if plan_storage > 0 else 0
        # L'admin n'a AUCUNE limite : son usage est compté, jamais plafonné.
        if (user.plan != "admin" and charge
                and user.storage_used + charge > plan_storage):
            charge = 0                      # quota plein : on journalise sans facturer
        doc = Document(user_id=user.id, original_name=filename, source_lang="auto",
                       target_lang=target_lang, original_path=original_path,
                       size_bytes=size, storage_charged=charge,
                       status="translating", paid=paid,
                       # Le quota mensuel SOMME cette colonne. Laissée à NULL
                       # (son ancien état), elle rendait tout quota de pages
                       # incomptable — donc invendable.
                       page_count=page_count,
                       reglages=json.dumps(reglages) if reglages else None)
        db.add(doc)
        user.storage_used += charge
        if usages or beta_charge:
            await db.flush()                # `doc.id` pour le lien
            for kind, n in usages:
                usage.record(db, user.id, doc.id, kind, n)
            if beta_charge:
                enrollment_id, cost = beta_charge
                beta.record(db, enrollment_id, doc.id, cost)
        await db.commit()
        # Lien job → Document : permet à `jobs.done`/`jobs.error` de reporter
        # `status`/`translated_path` à la fin du traitement (thread worker).
        jobs.set(job_id, document_id=doc.id)
    except Exception as e:
        await db.rollback()
        logger.error("Document non enregistré pour le job %s : %s", job_id, e)
        raise HTTPException(status_code=500,
                            detail="Impossible d'enregistrer la traduction. Réessayez.")


def qualite_autorisee(quality: str, precise: str, user: "User") -> str:
    """Mode de traduction effectif. Le mode précis (modèle de raisonnement, plus
    coûteux, même quota) est réservé aux admins : le serveur ne se fie pas à
    l'interface, `precise=1` ou `quality=precise` d'un autre compte → rapide."""
    if precise == "1":
        quality = "precise"
    if quality != "precise" or user.plan != "admin":
        return "fast"
    return "precise"


@router.post("/api/translate")
async def translate_endpoint(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    target_lang: str = Form("en"),
    format_options: str = Form("{}"),
    quality: str = Form("fast"),
    precise: str = Form(""),
    pages: str = Form(""),
    debug: str = Form(""),
    # « Traduire seulement les pages couvertes » : choix explicite de
    # l'utilisateur après un 402 `need_credits`. Sans lui, un solde insuffisant
    # refuse le document entier — jamais de troncature silencieuse.
    covered_only: str = Form(""),
    use_beta: str = Form("auto"),
    # Reprise d'un document arrêté (serveur coupé, pause, annulation) : ses pages déjà
    # traduites et déjà payées ne sont pas débitées une seconde fois.
    resume_of: str = Form(""),
    x_api_key: str = Header(None),
    # CONNEXION OBLIGATOIRE (décision produit) : un visiteur ne lance aucune
    # traduction. `optional_auth` laissait passer l'anonyme avec 1 page —
    # or la clé d'API est publique (elle est dans le bundle du frontend), donc
    # ce quota ne coûtait qu'un onglet de navigation privée à contourner.
    current_user: "User" = Depends(require_auth),
    db: "AsyncSession" = Depends(get_db),
):
    """Démarre un job de traduction et retourne immédiatement un job_id.
    Le client peut ensuite écouter /api/translate/events/{job_id} (SSE)
    pour suivre la progression, puis télécharger via /api/translate/result/{job_id}."""
    verify_api_key(x_api_key)
    # Appel direct (tests) : le défaut est l'objet `Form`, pas une chaîne.
    resume_of = resume_of if isinstance(resume_of, str) else ""

    quality = qualite_autorisee(quality, precise, current_user)

    filename = file.filename or ""
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Type non supporté : .{ext}")

    try:
        file_bytes = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Impossible de lire le fichier. Vérifiez qu'il n'est pas corrompu et réessayez.")

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"Fichier trop volumineux ({len(file_bytes)/(1024*1024):.1f} Mo, max 100 Mo).")

    try:
        format_opts = json.loads(format_options) if format_options else {}
    except json.JSONDecodeError:
        format_opts = {}

    # Mode STRUCTURE (debug) : aucune traduction. Reproduit exactement
    # test_extract_inject.py — extraction → translated = texte d'origine →
    # injection avec bordures de debug (contours de paragraphes). Sert à vérifier
    # le moteur dans l'interface, à l'identique des tests.
    debug_mode = str(debug).strip().lower() in ("1", "true", "yes", "on")

    # Mode de traduction (rapide vs précis) → modèle + budget de tokens.
    model, max_tokens = resolve_quality(quality)
    # Suffixe de cache : les deux modes produisent des résultats différents, ils
    # ne doivent JAMAIS partager le même translated.json ni le même PDF de sortie.
    qsuffix = "" if quality == "fast" else "_precise"
    if debug_mode:
        qsuffix = "_debug"   # n'écrase jamais une vraie traduction en cache

    # Sélection de pages (PDF/PPTX) : None = tout le document. Le jeton entre
    # dans toutes les clés de cache pour qu'une plage donnée ne réutilise jamais
    # le résultat d'une autre plage (ni du document entier).
    pages_set = parse_page_range(pages) if ext in ("pdf", "pptx") else None

    # ── Pages RÉELLEMENT traduisibles ────────────────────────────────────────
    #
    # Un PDF scanné est une suite d'images : aucun caractère n'y est
    # extractible, le moteur n'en tire rien et rend le document INCHANGÉ. La
    # facturation, elle, comptait les pages du conteneur. MESURÉ sur un scan
    # synthétique de trois pages : 3 pages débitées, 0 élément de texte extrait.
    # L'utilisateur payait, recevait son document tel quel, et son crédit avait
    # disparu — sans un mot, ni pour lui, ni dans le journal.
    #
    # Ce contrôle vient AVANT tout débit. C'est sa seule place utile : après, le
    # crédit est parti et le rembourser demanderait un chemin de compensation
    # qui n'existe pas.
    #
    # Les pages écartées ne sont pas perdues pour autant : `pages` ne découpe
    # pas le document, les pages hors sélection sont COPIÉES telles quelles
    # (cf. `translate_pdf_progressive`). L'utilisateur récupère donc son
    # document entier, ses pages scannées intactes, et ne paye que ce qui a pu
    # être traduit.
    # Compté UNE fois, avant le verrou : relire le conteneur sous le lock
    # retiendrait d'autant les autres requêtes du compte et ses webhooks.
    beta_choice = str(use_beta).strip().lower()
    beta_preview = (await beta.active_enrollment(db, current_user)
                    if beta_choice not in ("0", "false", "off") and ext in BETA_FORMATS else None)
    beta_mode = beta_preview is not None
    # Hors format bêta, la case n'a pas d'objet : traduction ordinaire.
    if beta_choice in ("1", "true") and not beta_mode and ext in BETA_FORMATS:
        return JSONResponse(status_code=402, content={
            "reason": "beta_inactive",
            "detail": "Votre accès bêta n'est pas actif. Utilisez votre forfait habituel ou consultez votre invitation.",
        })
    # Reprise PLAUSIBLE (document du compte, interrompu, en pause ou annulé) :
    # elle peut ne rien coûter, ses contrôles de solde viennent sous le
    # verrou, une fois le reste connu. Lecture sans verrou : un `resume_of` quelconque ne contourne
    # aucun contrôle préalable (OCR coûteux compris).
    if resume_of:
        _candidat = await db.get(Document, resume_of)
        if (_candidat is None or _candidat.user_id != current_user.id
                or _candidat.status not in STATUTS_REPRENABLES):
            resume_of = ""
    if (not beta_mode and not resume_of and current_user.plan == "free"
            and not current_user.email_verified and current_user.page_credits <= 0):
        raise HTTPException(403, "Vérifiez votre adresse e-mail pour utiliser les pages offertes.")
    try:
        # Les quotas bêta Office ont leurs propres unités ; leur extraction
        # est déjà mesurée ci-dessous. Le comptage normal n'appelle aucune IA.
        nb_pages = (1 if beta_mode and ext in ("docx", "xlsx") else
                    await run_in_threadpool(count_pages, file_bytes, ext))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if pages_set and any(p < 1 or p > nb_pages for p in pages_set):
        raise HTTPException(400, "La sélection contient une page absente du document.")
    beta_cost = None
    if beta_mode:
        if pages_set and any(p < 1 or p > nb_pages for p in pages_set):
            raise HTTPException(400, "La sélection contient une page absente du document.")
        try:
            beta_cost = (await run_in_threadpool(office_cost, file_bytes, ext)
                         if ext in ("docx", "xlsx") else BetaCost(ext, len(pages_set) if pages_set else nb_pages))
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        try:
            # Une reprise ne paie que son reste, connu sous le verrou
            # seulement : le contrôle qui fait foi est celui de plus bas.
            if not resume_of:
                await beta.check_cost(db, beta_preview, beta_cost)
        except HTTPException as exc:
            remaining = exc.detail["remaining"]
            if covered_only == "1" and ext in ("pdf", "pptx") and remaining > 0:
                selected = sorted(pages_set) if pages_set else range(1, nb_pages + 1)
                pages_set = set(list(selected)[:remaining])
                beta_cost = BetaCost(ext, len(pages_set))
            else:
                return JSONResponse(status_code=402, content={
                    **exc.detail, "detail": exc.detail["message"],
                    "partial_possible": ext in ("pdf", "pptx") and remaining > 0,
                    "pages_available": remaining,
                })
    lisibles = pages_avec_texte(file_bytes, ext)
    pages_ignorees = 0
    ocr_prepared = None
    ocr_pages = 0
    if lisibles is not None:
        visees_ocr = pages_set or set(range(1, nb_pages + 1))
        hors_essai = set()
        # L'OCR gratuit reste borné par la couverture disponible. Les pages
        # non reconnues restent comptées pour proposer l'achat ou un partiel
        # explicite, sans traiter un gros scan au-delà du budget.
        if not beta_mode and current_user.plan == "free":
            couverture = (await usage.free_pages_remaining(db, current_user)
                          + max(0, current_user.page_credits))
            bornees = set(sorted(visees_ocr)[:couverture])
            hors_essai = visees_ocr - bornees
            visees_ocr = bornees
        scans = visees_ocr - lisibles
        if scans:
            try:
                ocr_prepared, ocr_pages = await run_in_threadpool(prepare_scanned_pdf, file_bytes, scans)
            except OCRError as exc:
                return JSONResponse(status_code=exc.status_code, content={
                    "detail": str(exc), "reason": "scanned_document" if exc.status_code == 422 else "ocr_unavailable",
                    "pages_scanned": len(scans),
                })
            if len(ocr_prepared) > MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail="Le scan reconnu est trop volumineux. Selectionnez moins de pages.")
            lisibles = pages_avec_texte(ocr_prepared, ext) or set()
            qsuffix += f"_{OCR_VERSION}"
        # Non reconnues faute d'achat, pas illisibles : elles restent visées
        # (et comptées), l'achat rejoue le document avec l'OCR complet.
        lisibles |= hors_essai
    if lisibles is not None:
        visees = pages_set or set(range(1, nb_pages + 1))
        traduisibles = visees & lisibles

        if not traduisibles:
            # Rien à lire dans tout ce qui était visé : on refuse, et on ne
            # débite rien. `reason` distingue ce cas d'un refus de quota — le
            # client ne doit surtout pas proposer d'acheter des pages pour un
            # document qu'aucun achat ne rendra traduisible.
            #
            # `JSONResponse` et non `HTTPException(detail={...})` : FastAPI
            # emboîterait alors l'objet sous `detail`, or le client lit
            # `err.detail` comme un TEXTE à afficher. Il montrerait
            # « [object Object] » à l'utilisateur, et `err.reason` — qu'il lit
            # au premier niveau, comme pour `need_credits` — serait introuvable.
            return JSONResponse(
                status_code=422,
                content={
                    "detail": (
                        "La reconnaissance du scan n'a trouvé aucun texte lisible. "
                        "Aucune page n'a été décomptée. Réessayez avec un scan "
                        "plus net, contenant du texte imprimé en français ou en anglais."
                    ),
                    "reason": "scanned_document",
                    "pages_scanned": len(visees),
                },
            )

        if traduisibles != visees:
            # Document MIXTE. On ne touche à `pages_set` que dans ce cas : le
            # laisser à None quand tout est traduisible préserve les clés de
            # cache existantes (`pages_token`), qu'une sélection explicite
            # ferait diverger sans raison.
            pages_ignorees = len(visees) - len(traduisibles)
            pages_set = traduisibles
            logger.info(
                "Document mixte : %d page(s) sans texte extractible écartée(s) "
                "de la traduction et de la facturation.", pages_ignorees)

    # ── Limite de pages selon le plan ─────────────────────────────────────
    # On est dans un endpoint ASYNC : la session `db` et l'utilisateur
    # (`optional_auth`) sont déjà résolus par FastAPI. On interroge donc la base
    # par `await` direct — l'ancien code planifiait la coroutine sur la boucle
    # qui l'exécutait puis attendait le résultat en la bloquant (deadlock →
    # timeout 3 s → repli `free`), ce qui rétrogradait tout compte payant.
    plan = current_user.plan
    limit = get_plan_page_limit(plan)
    page_limit = limit if limit is not None else 999_999

    # Un document couvert par l'offre, le forfait, la bêta ou des crédits
    # achetés donne droit au résultat en clair. Les anciens aperçus verrouillés
    # gardent leur drapeau paid=False ; ils ne sont pas débloqués rétroactivement.
    doc_is_paid = False

    # Signaux anti-abus des pages OFFERTES : lus et enregistrés AVANT le verrou
    # (écritures courtes, validées tout de suite pour qu'un refus ne les perde
    # pas). Bêta et forfaits payants ne passent pas par ce contrôle.
    signals = machine_id = None
    known = True
    if not beta_mode and current_user.plan == "free":
        signals = anti_abus.client_signals(request)
        machine_id, known = await anti_abus.resolve_machine(db, signals)
        await db.commit()
        anti_abus.set_cookie(response, signals)

    def avec_cookie(rep):
        # Une JSONResponse renvoyée telle quelle ignore `response` : le cookie
        # de l'appareil doit être posé sur elle.
        if signals is not None:
            anti_abus.set_cookie(rep, signals)
        return rep

    # Verrou pessimiste sur la ligne User : compter puis insérer est un
    # lire-puis-écrire. Sans lock, deux requêtes simultanées du même compte
    # liraient le même solde et passeraient toutes deux. Le lock tient jusqu'au
    # commit de `_save_document_for_user` : la seconde attend, recompte, 402.
    #
    # `populate_existing` : l'authentification a déjà chargé cet utilisateur
    # dans la même session ; sans lui, la requête verrouille la ligne mais
    # rend l'objet en mémoire, avec le solde lu AVANT le verrou (double
    # dépense, ou pages créditées par un webhook écrasées au débit).
    locked = (await db.execute(
        select(User).where(User.id == current_user.id).with_for_update()
        .execution_options(populate_existing=True)
    )).scalar_one()
    # Pages déjà payées par le document arrêté (interrompu, en pause, annulé)
    # que l'on reprend. Lu SOUS
    # le verrou du compte : deux reprises simultanées du même document ne
    # peuvent pas toutes deux profiter de la remise. Le document doit être
    # celui du compte, reprenable, et du MÊME fichier vers la même langue :
    # le cache est partagé par fichier entre comptes, la remise, elle, ne vaut
    # que pour ce qu'on a soi-même payé.
    deja_payees = 0
    reprise = None
    if resume_of and not debug_mode:
        reprise = await db.get(Document, resume_of, with_for_update=True)
        file_hash = get_file_hash(file_bytes)
        if (reprise is None or reprise.user_id != locked.id
                or reprise.status not in STATUTS_REPRENABLES
                or reprise.target_lang != target_lang
                or os.path.basename(os.path.dirname(reprise.original_path or "")) != file_hash
                or reglages_de(reprise).get("qsuffix", qsuffix) != qsuffix
                or bool(reglages_de(reprise).get("precise")) != (quality == "precise")):
            reprise = None
        else:
            _job_dir, _lang_dir = build_job_paths(file_hash, target_lang)
            total = len(pages_set) if pages_set else nb_pages
            # Payé par ce document ET par ceux qu'il reprenait déjà.
            payees = (await usage.pages_payees(db, reprise.id)
                      + int(reglages_de(reprise).get("deja") or 0))
            if await beta.office_billed(db, reprise.id):
                payees = total      # DOCX/XLSX bêta payé et écrit : tout est dû
            deja_payees = min(payees, pages_faites(
                translation_path_for(_lang_dir, ext, pages_set, qsuffix),
                ext, pages_set, total))
            # Consommé : une seconde reprise du même document paiera plein
            # tarif. Annulé avec la transaction si la reprise est refusée.
            # Sans remise, le document garde son statut d'arrêt : rien n'a été
            # transmis à la reprise.
            if deja_payees > 0:
                reprise.status = "resumed"
    beta_charge = None
    if beta_mode:
        enrollment = await beta.active_enrollment(db, locked, lock=True)
        if enrollment is None:
            return JSONResponse(status_code=402, content={
                "reason": "beta_inactive", "detail": "Votre accès bêta a expiré ou a été révoqué.",
            })
        if ext in ("pdf", "pptx"):
            beta_cost = BetaCost(ext, max(0, (len(pages_set) if pages_set else nb_pages)
                                          - deja_payees))
        elif deja_payees:
            beta_cost = BetaCost(ext, 0)        # traduction déjà écrite : rien à refaire
        try:
            await beta.check_cost(db, enrollment, beta_cost)
        except HTTPException as exc:
            return JSONResponse(status_code=402, content={**exc.detail, "detail": exc.detail["message"]})
        beta_charge = (enrollment.id, beta_cost)
        usages = []
        doc_is_paid = True
    else:
        solde = max(0, locked.page_credits)
        gratuit = locked.plan == "free"
        if gratuit:
            reste_plan = await usage.free_pages_remaining(db, locked)
        else:
            monthly = get_plan_monthly_pages(locked.plan)
            reste_plan = (None if monthly is None else
                          max(0, monthly - await usage.pages_used_this_month(db, locked)))
        needed = max(0, (len(pages_set) if pages_set else nb_pages) - deja_payees)
        if (resume_of and needed and gratuit and not locked.email_verified
                and solde <= 0):
            raise HTTPException(403, "Vérifiez votre adresse e-mail pour utiliser les pages offertes.")
        # Pages offertes refusées (abus probable) : seules les pages achetées
        # restent utilisables.
        refus_offert = None
        if gratuit and reste_plan > 0 and signals is not None:
            refus_offert = await anti_abus.free_risk(
                db, locked, signals, machine_id, known, min(needed, reste_plan))
            if refus_offert:
                reste_plan = 0
        couvert = None if reste_plan is None else reste_plan + solde
        if couvert is not None and needed > couvert:
            # Pas de reprise tronquée : une autre sélection nommerait un
            # autre cache, et les pages payées ne seraient pas retrouvées.
            partiel = ext in ("pdf", "pptx") and couvert > 0 and deja_payees == 0
            if not (covered_only == "1" and partiel):
                if refus_offert:
                    return avec_cookie(JSONResponse(status_code=402, content={
                        "reason": "free_limit_device", "risk": refus_offert,
                        "detail": "Les pages offertes ne sont pas disponibles pour ce compte "
                                  "sur cet appareil. Vous pouvez acheter des pages pour continuer.",
                        "pages_needed": needed, "pages_available": couvert,
                        "pages_missing": needed - couvert, "partial_possible": partiel,
                    }))
                detail = (f"Crédits insuffisants pour traduire tout le document : "
                          f"il demande {needed} page(s) équivalente(s), {couvert} couverte(s).")
                _debut, repart = usage.quota_period(locked)
                detail += f" Le quota du forfait repart le {repart:%d/%m/%Y}."
                return avec_cookie(JSONResponse(status_code=402, content={
                    "detail": detail, "reason": "need_credits",
                    "pages_needed": needed, "pages_available": couvert,
                    "pages_missing": needed - couvert,
                    "partial_possible": partiel,
                    "trial": gratuit and reste_plan > 0,
                }))
            visees = sorted(pages_set) if pages_set else range(1, nb_pages + 1)
            pages_set = set(list(visees)[:couvert])
            needed = couvert

        pages_set = cap_pages_for_plan(pages_set, ext, page_limit)
        du_plan = needed if reste_plan is None else min(needed, reste_plan)
        achetees = needed - du_plan
        locked.page_credits -= achetees
        if gratuit and du_plan > 0 and signals is not None:
            anti_abus.record_grant(db, locked, signals, machine_id, du_plan)
        # Réservation atomique avant le worker : effacer un document ne rend
        # aucun quota, et le mécanisme existant rembourse un échec une seule fois.
        kind = KIND_FREE_OFFER if gratuit else KIND_PLAN
        usages = [(k, n) for k, n in ((kind, du_plan), (KIND_CREDITS, achetees)) if n > 0]
        doc_is_paid = True

    # Ce qui sera RÉELLEMENT traduit — enregistré sur le Document, sinon le
    # quota du mois prochain n'aurait rien à compter (`page_count` restait NULL).
    pages_facturees = len(pages_set) if pages_set else nb_pages

    ptok = pages_token(pages_set)
    psuffix = f"_{ptok}" if ptok else ""

    file_hash = get_file_hash(file_bytes)
    safe_name = sanitize_filename(filename)
    job_dir, lang_dir = build_job_paths(file_hash, target_lang)
    os.makedirs(lang_dir, exist_ok=True)

    original_path = os.path.join(job_dir, f"original.{ext}")
    extraction_path = os.path.join(job_dir, f"extraction{psuffix}.json")
    # LA traduction persistante — la sortie DeepSeek, seule chose coûteuse à
    # reconstituer. Pour le PDF, c'est le JSON du moteur v2 (texte + décisions
    # de page) ; pour DOCX/PPTX, le JSON de traduction. Le PDF/DOCX rendu, lui,
    # n'est PAS conservé : il se recalcule à la demande depuis ces deux-là.
    translation_path = translation_path_for(lang_dir, ext, pages_set, qsuffix)

    output_filename = f"{safe_name}_TRADUIT{qsuffix}{psuffix}.{ext}"
    if debug_mode:
        output_filename = f"{safe_name}_STRUCTURE{psuffix}.{ext}"
    if format_opts.get("mode") and format_opts["mode"] != "preserve":
        output_filename = f"{safe_name}_TRADUIT{qsuffix}{psuffix}_{format_opts['mode']}.{ext}"
    layout_opts = format_opts.get("layout")
    if layout_opts:
        import hashlib as _hl
        layout_sig = _hl.sha1(json.dumps(layout_opts, sort_keys=True).encode()).hexdigest()[:10]
        base, dot, fext = output_filename.rpartition(".")
        output_filename = f"{base}_L{layout_sig}{dot}{fext}"

    job_id = jobs.create()
    # Rendu TRANSITOIRE, propre au job (nettoyé par le GC) : il sert le flux
    # progressif et le téléchargement immédiat, puis disparaît. La source de
    # vérité reste `translation_path`.
    output_path = os.path.join(lang_dir, f"render{qsuffix}{psuffix}_{job_id[:8]}.{ext}")
    # `user_id` : proprietaire, dont /partial et /result se servent.
    # `pages` : pages RÉELLEMENT traduites, les seules à protéger dans
    # l'aperçu d'essai (les autres sont des copies de l'original).
    jobs.set(job_id, user_id=current_user.id,
             pages=set(pages_set) if pages_set else None)
    if ext == "pdf":
        # PDF → moteur v2 PROGRESSIF : page traduite = page affichable.
        # `partial` grandit page à page ; `translation_path` (pages.json) = la
        # traduction persistante, qui sert aussi de cache de reprise.
        partial_path = os.path.join(lang_dir, f"partial{qsuffix}{psuffix}_{job_id[:8]}.pdf")
        target = run_pdf_v2_job
        job_args = (job_id, file_bytes, original_path, output_path,
                    output_filename, partial_path, translation_path, target_lang,
                    pages_set, debug_mode, ocr_prepared)
    elif ext == "pptx":
        # PPTX → moteur progressif slide par slide (comme le PDF v2).
        # Si compte admin : 5 slides traduites en parallèle.
        partial_path = os.path.join(lang_dir, f"partial{qsuffix}{psuffix}_{job_id[:8]}.pdf")
        is_admin = (current_user.plan == "admin")
        target = run_pptx_progressive_job
        job_args = (job_id, file_bytes, original_path, output_path,
                    output_filename, partial_path, translation_path, target_lang,
                    pages_set, debug_mode, is_admin)
    elif ext == "xlsx":
        # XLSX → aperçu progressif FEUILLE PAR FEUILLE. La traduction, elle,
        # reste d'un bloc : `sharedStrings.xml` est commun à tout le classeur
        # et une même chaîne peut servir dix feuilles, donc aucune ne peut la
        # revendiquer. C'est l'AFFICHAGE qui est progressif, pas la traduction.
        partial_path = os.path.join(lang_dir, f"partial{qsuffix}{psuffix}_{job_id[:8]}.pdf")
        target = run_xlsx_progressive_job
        job_args = (job_id, file_bytes, original_path, output_path,
                    output_filename, partial_path, translation_path, target_lang,
                    model, max_tokens, debug_mode)
    else:
        target = run_translation_job
        job_args = (job_id, file_bytes, filename, ext, target_lang, format_opts,
                    job_dir, lang_dir, original_path, extraction_path,
                    translation_path, output_path, output_filename,
                    model, max_tokens, pages_set, debug_mode)
    # ── Document en base AVANT de démarrer le worker ─────────────────────
    # L'ordre est un garde-fou, pas un détail : la ligne Document est la seule
    # référence qui protège les octets partagés du magasin contre la purge d'un
    # autre compte (`_purge_if_orphan` compte les références en base). Insérer
    # après `thread.start()` ouvrait deux fenêtres : (1) A supprime son document
    # pendant que le job de B démarre → les fichiers communs sont purgés sous
    # ses pieds ; (2) un cache-hit terminait le job avant que `document_id` ne
    # soit lié → le Document restait « translating » pour toujours.
    try:
        # L'original est posé ICI, pas par le worker : un job mis en pause ou
        # annulé avant de démarrer doit rester reprenable, donc avoir son
        # original sur disque (la reprise le relit).
        await run_in_threadpool(_sauver_original, original_path, file_bytes)
        await _save_document_for_user(current_user, db, job_id, filename,
                                      target_lang, original_path, len(file_bytes),
                                      paid=doc_is_paid, page_count=pages_facturees,
                                      usages=usages, beta_charge=beta_charge,
                                      reglages={
                                          # Sélection EFFECTIVE (après pages
                                          # scannées et pages couvertes) : celle
                                          # qui nomme le cache de reprise.
                                          "pages": ",".join(map(str, sorted(pages_set)))
                                                   if pages_set else "",
                                          "precise": quality == "precise",
                                          "qsuffix": qsuffix,
                                          "beta": bool(beta_charge),
                                          "deja": deja_payees})
    except Exception:
        # Rien ne sera soumis : le job ouvert plus haut resterait « pending »
        # en mémoire, sans document ni worker, jusqu'au ménage.
        jobs.forget(job_id)
        raise
    # Reposé après l'enregistrement : la suppression par un autre compte d'un
    # document de même empreinte a pu purger l'original entre-temps (sans effet
    # s'il est là). Le premier appel reste nécessaire : s'il échoue, aucun
    # document n'est enregistré.
    await run_in_threadpool(_sauver_original, original_path, file_bytes)

    # File de PRIORITÉ, plus de thread lancé à la volée : l'ordonnanceur place le
    # job selon le niveau du plan (admin > pro > starter > gratuit) et le fait
    # démarrer dès qu'un worker se libère. Soumis APRÈS l'insertion du Document,
    # pour la même raison que l'ancien `thread.start()` venait après.
    scheduler.submit(job_id, get_plan_priority(current_user.plan), target, job_args)

    logger.info(f"Job {job_id} queued for '{filename}' -> {target_lang} "
                f"(priorité {get_plan_priority(current_user.plan)})")
    # `pages_ignorees` : pages sans texte extractible, écartées de la traduction
    # ET de la facturation. Renvoyé pour que l'interface puisse le DIRE — sans
    # cela, l'utilisateur d'un document mixte verrait des pages revenir
    # inchangées sans comprendre pourquoi, et croirait à une traduction ratée
    # là où il s'agit d'un scan qu'on n'a pas facturé.
    reponse = {"job_id": job_id, "can_download": doc_is_paid}
    if ocr_pages:
        reponse["ocr_pages"] = ocr_pages
        reponse["ocr_review_required"] = True
    if pages_ignorees:
        reponse["pages_ignorees"] = pages_ignorees
    return avec_cookie(JSONResponse(reponse))


@router.get("/api/translate/events/{job_id}")
async def translation_events(job_id: str, token: str = ""):
    """SSE endpoint : émet les events de progression jusqu'à done/error/stopped.

    EventSource (navigateur) ne supporte pas les headers custom : le JWT passe
    donc en QUERY (`?token=`). S'appuyer sur le seul job_id laissait le flux
    sans AUCUNE authentification — pas d'octets du document, mais le nom du
    fichier et la progression d'autrui, et surtout la file d'événements est à
    consommateur UNIQUE : un tiers branché sur le flux VOLE les événements du
    client légitime. On répond 404 (pas 403) pour ne pas révéler l'existence
    du job. Le middleware ne journalise que le path, jamais la query : le
    token ne fuit pas dans les logs.
    """
    try:
        payload = verify_access_token(token)
        user_id = payload["sub"]
    except Exception:
        raise HTTPException(status_code=404, detail="Job introuvable.")

    job = jobs.get(job_id)
    if not job or job.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Job introuvable.")

    async def event_stream():
        q: queue.Queue = job["q"]
        while True:
            try:
                # Lecture non-bloquante avec délai pour laisser respirer l'event loop
                try:
                    msg = q.get(timeout=0.2)
                except queue.Empty:
                    # Le client se RECONNECTE après une coupure : si le flux
                    # coupé avait déjà consommé l'événement final, la file est
                    # vide pour toujours. On le reconstitue depuis l'état du job.
                    etat = job.get("state")
                    if etat in ("done", "error", *STATUTS_ARRET):
                        fin = ({"type": "done", "filename": job.get("result_filename")}
                               if etat == "done" else
                               {"type": "error", "message": job.get("error")}
                               if etat == "error" else
                               {"type": "stopped", "mode": etat})
                        yield f"data: {json.dumps(fin, ensure_ascii=False)}\n\n"
                        break
                    yield ": keepalive\n\n"
                    await asyncio.sleep(0.1)
                    continue

                data = json.dumps(msg, ensure_ascii=False)
                yield f"data: {data}\n\n"

                if msg.get("type") in ("done", "error", "stopped"):
                    break
            except asyncio.CancelledError:
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _job_of(job_id: str, user: "User"):
    """Le job `job_id`, s'il appartient bien à `user`.

    Le contrôle de propriété est INDISPENSABLE : la clé d'API voyage dans le
    bundle du frontend, elle est donc publique. Sans ce garde, un `job_id`
    deviné suffisait à lire le document d'un autre compte. On répond 404 (et
    non 403) pour ne pas révéler l'existence du job.
    """
    job = jobs.get(job_id)
    if not job or job.get("user_id") != user.id:
        raise HTTPException(status_code=404, detail="Job introuvable.")
    return job


@router.post("/api/translate/{job_id}/{mode}")
async def translation_stop(job_id: str, mode: Literal["pause", "cancel"],
                           x_api_key: str = Header(None),
                           current_user: "User" = Depends(require_auth)):
    """DEMANDE de pause ou d'annulation d'une traduction, par son propriétaire.

    La réponse confirme la demande, pas l'état final. Un job encore en file
    s'arrête tout de suite ; un job en cours finit sa page (ou son lot) et
    s'arrête au point de contrôle suivant. Dans les deux cas le flux émet
    `stopped`. Les pages traduites restent débitées, le reste est rendu ; le
    document se reprend sur le cache (« Reprendre » ne débite que le reste)."""
    verify_api_key(x_api_key)
    statut = dict(zip(("pause", "cancel"), STATUTS_ARRET))[mode]
    _job_of(job_id, current_user)
    ou = jobs.demander_arret(job_id, statut)
    if ou is None:
        raise HTTPException(status_code=409,
                            detail="Traduction déjà terminée ou déjà arrêtée.")
    if ou == "en_file":
        # Aucun worker ne le tient : rien à attendre, on le consigne ici.
        await run_in_threadpool(jobs.arreter, job_id, statut)
    return {"job_id": job_id, "status": statut}


async def _droit_au_clair(job: dict, user: "User", db: AsyncSession) -> bool:
    """Ce compte peut-il lire CE job en clair ? Même règle que les routes de
    `documents` (`_may_read_clear`) : l'abonnement OU l'achat de ce document.
    Lire le seul plan refusait le clair à un compte gratuit qui venait de
    payer précisément cette traduction."""
    if is_paid_plan(user.plan):
        return True
    doc_id = job.get("document_id")
    doc = await db.get(Document, doc_id) if doc_id else None
    return doc is not None and doc.user_id == user.id and _may_read_clear(user, doc)


@router.get("/api/translate/partial/{job_id}")
async def translation_partial(job_id: str, x_api_key: str = Header(None),
                              current_user: "User" = Depends(require_auth),
                              db: AsyncSession = Depends(get_db)):
    """PDF PARTIEL d'un job v2 en cours : contient les pages 1..k déjà
    traduites (réécrit atomiquement après chaque page). Le client le recharge
    à chaque événement `page done` pour afficher la traduction au fil de l'eau."""
    verify_api_key(x_api_key)
    job = _job_of(job_id, current_user)
    path = job.get("partial_path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=202, detail="Aucune page prête pour l'instant.")
    # Lue AVANT le fichier : le runner l'écrit après lui, elle ne peut donc
    # qu'être en retard sur le contenu, jamais annoncer une page absente.
    pages_pretes = job.get("partial_pages")
    # Lecture et rastérisation HORS de la boucle : appelé à chaque page du
    # flux, un appel bloquant ici figeait toute l'application, SSE compris.
    from app.api.documents import _lire
    data = await run_in_threadpool(_lire, path)

    # PLAN D'ESSAI : jamais le clair. On envoyait le PDF traduit tel quel et on
    # comptait sur le navigateur pour l'assombrir — mesuré : un compte `free`
    # récupérait le FICHIER (782 mots extractibles) en trois clics dans l'onglet
    # Réseau. Rastériser retire la couche texte : il ne reste que des pixels
    # filigranés, inexploitables sans OCR. Le projecteur au survol, lui, marche
    # toujours (il lui faut des pixels nets, il en a).
    # Liste d'AUTORISATION, pas de refus : un plan inconnu (valeur corrompue,
    # plan retiré du barème) est traité comme non payant. `== FREE_PLAN`
    # donnait l'inverse : tout ce qui n'était pas littéralement "free" passait.
    if not await _droit_au_clair(job, current_user, db):
        data = await run_in_threadpool(rasterize_for_trial, data, job.get("pages"))

    headers = {"Cache-Control": "no-store"}
    if pages_pretes is not None:
        # Pages réellement traduites DANS ce fichier (PPTX) : le client n'a
        # plus à les déduire des événements, qui peuvent se perdre.
        headers["X-Pages-Pretes"] = ",".join(map(str, pages_pretes))
    return Response(content=data, media_type="application/pdf", headers=headers)


@router.get("/api/translate/result/{job_id}")
async def translation_result(job_id: str, x_api_key: str = Header(None),
                             current_user: "User" = Depends(require_auth),
                             db: AsyncSession = Depends(get_db)):
    """Retourne le fichier traduit une fois le job terminé.

    TÉLÉCHARGEMENT RÉSERVÉ AUX PLANS PAYANTS (décision produit). Le verrou
    n'existait que dans le frontend (bouton qui renvoyait vers la grille
    tarifaire) : un appel direct rendait le PDF complet à n'importe qui. Un
    verrou qui n'est pas appliqué par le serveur n'est pas un verrou.
    """
    verify_api_key(x_api_key)
    job = _job_of(job_id, current_user)
    if not await _droit_au_clair(job, current_user, db):
        raise HTTPException(
            status_code=402,
            detail="Forfait Gratuit : téléchargement indisponible. "
                   "Passez à Starter pour télécharger vos traductions.",
        )
    if job["state"] == "error":
        raise HTTPException(status_code=500, detail="La traduction a échoué. Réessayez ou contactez le support si le problème persiste.")
    if job["state"] in STATUTS_ARRET:
        # État final : 202 ferait redemander le client sans fin. Les pages
        # déjà traduites se récupèrent depuis la bibliothèque.
        raise HTTPException(status_code=409, detail="Traduction arrêtée : retrouvez les pages déjà traduites dans votre bibliothèque.")
    if job["state"] != "done":
        raise HTTPException(status_code=202, detail="Job en cours.")
    if not job["result_path"] or not os.path.exists(job["result_path"]):
        raise HTTPException(status_code=500, detail="Fichier résultat introuvable.")

    return FileResponse(
        job["result_path"],
        media_type="application/octet-stream",
        filename=job["result_filename"],
    )
