import os
import json
import time
import glob
import asyncio
import logging
import uuid
import queue
import threading
import shutil
import hashlib
import subprocess
import tempfile
import fitz                # assemblage du PDF partiel, page par page
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, status, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, Response
from dotenv import load_dotenv

# Charger .env depuis le dossier backend/, quel que soit le cwd
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_env_path)

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
logger = logging.getLogger("backend_app")

# Sous `uvicorn --reload`, ce module est importé DEUX fois : dans le process
# parent (qui appelle load_app() pour échouer vite) et dans le worker. Les
# messages d'init sont donc empilés ici puis émis dans le lifespan, que seul le
# worker traverse — sinon chaque ligne apparaît en double au démarrage.
_STARTUP_NOTES: list[tuple[int, str]] = []


async def _reconcilier_jobs_orphelins():
    """Clôt les Documents restés `translating` d'un processus précédent.

    Le registre des jobs (`_jobs`) vit en MÉMOIRE : il est vide au démarrage.
    Tout Document encore `translating` à cet instant a donc perdu son worker —
    serveur arrêté, rechargement, plantage. Aucune heuristique là-dedans, aucun
    délai à deviner : c'est vrai par construction.

    Sans ça, la ligne reste en vol POUR TOUJOURS. L'utilisateur voit un document
    éternellement « en cours » dans sa bibliothèque, et comme `translated_path`
    est NULL, le téléchargement lui sert l'ORIGINAL en silence — un document
    présenté comme traduit qui ne l'est pas. Mesuré sur cette base : 1 zombie
    de 08:11 que rien n'aurait jamais nettoyé.
    """
    # LIMITE ASSUMÉE : si un second processus démarre pendant qu'un premier
    # traduit encore, il marquera en erreur un job bien vivant. Le dégât est
    # transitoire — le worker du premier appellera `_job_done`, qui repasse la
    # ligne à `done` avec son `translated_path`. On ne complique pas pour ça.
    try:
        from database import async_session
        from models import Document
        from sqlalchemy import update
        async with async_session() as db:
            r = await db.execute(
                update(Document)
                .where(Document.status == "translating")
                .values(status="error")
                .returning(Document.id)
            )
            perdus = len(r.fetchall())
            await db.commit()
        if perdus:
            logger.warning(
                f"{perdus} traduction(s) interrompue(s) par un arrêt précédent : "
                f"marquée(s) en erreur."
            )
    except Exception as e:
        # Ne JAMAIS empêcher le serveur de démarrer pour un ménage.
        logger.warning(f"Réconciliation des jobs orphelins impossible : {e}")


def _balayer_partiels_orphelins() -> None:
    """Efface les `partial_*.pdf` d'un processus précédent.

    Un PDF partiel n'appartient qu'à UN job, et les jobs vivent en mémoire :
    au démarrage, tout partiel présent sur le disque est orphelin par
    construction (même raisonnement que `_reconcilier_jobs_orphelins`). Sans ce
    balayage ils s'accumulaient et maintenaient leur dossier en vie.
    """
    efface = 0
    for path in glob.glob(os.path.join(TRANSLATIONS_DIR, "**", "partial_*.pdf"),
                          recursive=True):
        try:
            os.remove(path)
            efface += 1
        except OSError:
            pass
    if efface:
        logger.info(f"{efface} PDF partiel(s) orphelin(s) balayé(s).")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    for _level, message in _STARTUP_NOTES:
        print(message, flush=True)
    await _reconcilier_jobs_orphelins()
    _balayer_partiels_orphelins()
    yield

FRONTEND_API_KEY = os.getenv("FRONTEND_API_KEY", "precis_frontend_secure_key_2026_xK9mP2vL")
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 Mo
ALLOWED_EXTENSIONS = {"txt", "pdf", "docx", "pptx"}

TRANSLATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translations")
os.makedirs(TRANSLATIONS_DIR, exist_ok=True)

def get_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()[:12]

def sanitize_filename(name: str) -> str:
    stem = os.path.splitext(name)[0]
    cleaned = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in stem)
    cleaned = "_".join(cleaned.split())
    return cleaned[:50] or "document"

def parse_page_range(s: str):
    """Convertit une saisie de plage de pages ('1-5, 8, 11-13') en un ensemble
    de numéros 1-basés {1,2,3,4,5,8,11,12,13}. Retourne None si vide
    (= toutes les pages). Les jetons invalides sont ignorés silencieusement."""
    if not s or not s.strip():
        return None
    pages: set[int] = set()
    for tok in s.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if "-" in tok:
            a, _, b = tok.partition("-")
            try:
                a, b = int(a.strip()), int(b.strip())
            except ValueError:
                continue
            if a > b:
                a, b = b, a
            for p in range(a, b + 1):
                if p >= 1:
                    pages.add(p)
        else:
            try:
                p = int(tok)
            except ValueError:
                continue
            if p >= 1:
                pages.add(p)
    return pages or None

def pages_token(pages_set) -> str:
    """Jeton de cache déterministe pour une sélection de pages. Lisible quand la
    sélection est une plage contiguë ('p3-5', 'p7'), sinon un hash court. Vide
    si aucune sélection (préserve les caches existants 'toutes les pages')."""
    if not pages_set:
        return ""
    sp = sorted(pages_set)
    if sp == list(range(sp[0], sp[-1] + 1)):
        return f"p{sp[0]}" if sp[0] == sp[-1] else f"p{sp[0]}-{sp[-1]}"
    return "p" + hashlib.sha1(",".join(map(str, sp)).encode()).hexdigest()[:8]

# ── Conversion PDF pour l'aperçu ────────────────────────────────────────────────
# L'aperçu côte-à-côte s'appuie sur pdf.js : pour obtenir un rendu EXACT des
# formats non-PDF (DOCX, PPTX, TXT), on les convertit en PDF via LibreOffice
# headless. La conversion ne sert QUE l'aperçu — le téléchargement garde le
# format d'origine. Résultats mis en cache disque (clé = hash du contenu).
PREVIEW_CACHE_DIR = os.path.join(TRANSLATIONS_DIR, "_previews")
_preview_lock = threading.Lock()

# NOTE — une file PRIORITAIRE a été écrite ici, puis retirée.
#
# L'idée : faire passer les conversions qu'un écran attend devant celles du
# travail de fond, en soupçonnant que le panneau source restait blanc parce
# qu'il était affamé derrière le convertisseur de partiel. Le test de mutation a
# tranché : en NEUTRALISANT la priorité, aucun contrôle ne tombait. `Lock` de
# CPython réveille déjà le thread en attente au premier relâchement — le
# mécanisme ne changeait donc rien, et la vraie cause était ailleurs (le partiel
# n'était jamais écrit, cf. `_write_pptx_pdf_partial`).
#
# Un mécanisme dont on ne peut pas prouver qu'il agit ne se garde pas : il ne
# se lit plus comme du code, mais comme une intention.

def _find_soffice():
    candidates = [
        os.getenv("SOFFICE_PATH"),
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "soffice",
        "libreoffice",
    ]
    for c in candidates:
        if not c:
            continue
        if os.path.isabs(c):
            if os.path.exists(c):
                return c
        else:
            found = shutil.which(c)
            if found:
                return found
    return None

SOFFICE_PATH = _find_soffice()
if SOFFICE_PATH:
    _STARTUP_NOTES.append((logging.INFO, f"LibreOffice  ~  {SOFFICE_PATH}"))
else:
    _STARTUP_NOTES.append((logging.WARNING, "LibreOffice introuvable : l'aperçu des formats non-PDF sera indisponible."))

def convert_to_pdf_bytes(file_bytes: bytes, ext: str,
                         use_cache: bool = True) -> bytes:
    """Convertit un document en PDF (bytes) pour l'aperçu. Les PDF sont
    renvoyés tels quels. Lève une exception si la conversion échoue.

    `use_cache=False` pour les documents JETABLES et uniques — le PPTX partiel
    d'un job, qui change à chaque diapositive traduite : le mettre en cache
    emplirait `_previews` d'un fichier par état intermédiaire, dont aucun ne
    resservira jamais.
    """
    if ext == "pdf":
        return file_bytes

    cache_path = None
    if use_cache:
        file_hash = get_file_hash(file_bytes)
        os.makedirs(PREVIEW_CACHE_DIR, exist_ok=True)
        cache_path = os.path.join(PREVIEW_CACHE_DIR, f"{file_hash}.pdf")
        if os.path.exists(cache_path):
            with open(cache_path, "rb") as f:
                return f.read()

    if not SOFFICE_PATH:
        raise RuntimeError("LibreOffice est requis pour convertir ce format en PDF.")

    # `ignore_cleanup_errors` — LibreOffice garde son profil (`profile/user/…`)
    # ouvert quelques instants APRÈS avoir rendu la main. Sous Windows, effacer
    # un fichier encore ouvert lève `PermissionError` : sans ce drapeau, une
    # conversion RÉUSSIE échouait au nettoyage, et l'erreur remontait comme si
    # la conversion elle-même avait échoué. Ce qui reste est du temporaire, que
    # le système récupère.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        src_path = os.path.join(tmp, f"input.{ext}")
        with open(src_path, "wb") as f:
            f.write(file_bytes)
        profile_uri = "file:///" + os.path.join(tmp, "profile").replace(os.sep, "/")
        cmd = [
            SOFFICE_PATH, "--headless", "--norestore", "--nolockcheck",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to", "pdf", "--outdir", tmp, src_path,
        ]
        # LibreOffice supporte mal les invocations concurrentes : on sérialise.
        with _preview_lock:
            proc = subprocess.run(cmd, capture_output=True, timeout=120)
        out_path = os.path.join(tmp, "input.pdf")
        if proc.returncode != 0 or not os.path.exists(out_path):
            err = proc.stderr.decode("utf-8", "ignore")[:300]
            raise RuntimeError(f"Conversion LibreOffice échouée : {err}")
        with open(out_path, "rb") as f:
            data = f.read()

    if cache_path:
        with open(cache_path, "wb") as f:
            f.write(data)
    return data

app = FastAPI(title="Précis Translator API", version="1.0.0", lifespan=lifespan)

origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8000,http://127.0.0.1:5173,http://127.0.0.1:8000,http://localhost:3000,http://localhost:3001,http://127.0.0.1:3001")
origins = [o.strip() for o in origins_str.split(",") if o.strip()]
dev_origins = ["http://localhost:5173","http://localhost:3000","http://localhost:3001","http://127.0.0.1:5173","http://127.0.0.1:3000","http://127.0.0.1:3001"]
origins = list(set(origins + dev_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes auth & documents (comptes utilisateurs) ───────────────────────────
from routes.auth import router as auth_router
from routes.documents import router as documents_router
from routes.payments import router as payments_router
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(payments_router)

# ── Route quota stockage ─────────────────────────────────────────────────────
from auth import require_auth, verify_access_token
import render_cache
import runtags        # invariants de traduction (balises, cohérence des termes)
from pricing import (zone_for_country, CURRENCY, CURRENCY_DECIMALS,
                     page_price, plan_price)
from models import (User, Document, get_plan_page_limit, get_plan_storage,
                    get_plan_monthly_pages, PLAN_LABELS,
                    is_paid_plan)
from preview import rasterize_for_trial
from database import get_db
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

@app.get("/api/user/storage")
async def user_storage(
    user: User = Depends(require_auth),
):
    return {
        "used": user.storage_used,
        # Dérivé du plan, jamais de la colonne — même raison que dans
        # `_user_response` : c'est `get_plan_storage` qui arbitre à l'écriture.
        "limit": get_plan_storage(user.plan),
        "plan": user.plan,
    }

@app.get("/api/pricing")
async def pricing(request: Request, country: str | None = None):
    """Grille tarifaire pour la zone de l'appelant.

    Le frontend n'embarque AUCUN prix : il affiche ce que cette route renvoie.
    Dupliquer la grille dans `PricingCards.tsx`, c'était garantir qu'un jour la
    carte annoncerait un montant que l'écran de paiement ne pratiquerait plus.

    La localisation vient de l'en-tête posé par le proxy (`CF-IPCountry` chez
    Cloudflare). Sans proxy géo, il n'y a pas de pays : on retombe alors sur le
    tarif PLEIN. Se tromper en faveur du client sur une remise de pouvoir
    d'achat serait une perte sèche et silencieuse ; se tromper en sa défaveur
    est visible et se corrige.

    `country` en paramètre ne sert qu'à la mise au point et aux tests — il est
    fourni par le client, donc n'importe qui peut réclamer la zone la moins
    chère. Ce n'est PAS un contrôle : au moment d'encaisser, la zone devra être
    reconfirmée côté serveur à partir du moyen de paiement réellement utilisé.
    """
    detected = (
        country
        or request.headers.get("CF-IPCountry")
        or request.headers.get("X-Country")
    )
    zone = zone_for_country(detected)
    currency = CURRENCY[zone]

    return {
        "zone": zone,
        "currency": currency,
        "decimals": CURRENCY_DECIMALS[currency],
        "page_price": page_price(zone),
        "plans": [
            {
                "key": key,
                "label": PLAN_LABELS.get(key, key),
                "monthly": plan_price(key, zone, annual=False),
                "annual": plan_price(key, zone, annual=True),
                "monthly_pages": get_plan_monthly_pages(key),
                "storage": get_plan_storage(key),
            }
            for key in ("free", "starter", "pro", "enterprise")
        ],
    }


try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except ImportError:
    limiter = None
    _STARTUP_NOTES.append((logging.WARNING, "Slowapi absent : limitation de débit désactivée."))

def rate_limit_decorator(limit_str: str):
    if limiter:
        return limiter.limit(limit_str)
    return lambda f: f

@app.middleware("http")
async def log_requests(request: Request, call_next):
    ip = request.client.host if request.client else "unknown"
    logger.info(f"Incoming request from IP: {ip} | Method: {request.method} | Path: {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response status for IP {ip}: {response.status_code}")
    return response

def verify_api_key(x_api_key: str = None):
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header")
    if x_api_key != FRONTEND_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid X-API-Key")

from docx_translator_engine import DOCXTranslatorEngine
try:
    from pptx_translator_engine import PPTXTranslatorEngine
except ImportError as _e:
    PPTXTranslatorEngine = None
    _STARTUP_NOTES.append((logging.WARNING, f"PPTX indisponible : {_e}"))
from translator_ai import TranslatorAI

# ── Moteur PDF v2 (pdf_engine_v2) : traduction PROGRESSIVE page par page ─────
# extraction → traduction → rendu PAR PAGE ; le PDF partiel grandit au fil des
# pages et le client l'affiche sans attendre la fin. L'ancien moteur
# (pdf_translator_engine) n'est plus branché sur les PDF.
import sys as _sys
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in _sys.path:
    _sys.path.insert(0, _REPO_ROOT)
from pdf_engine_v2 import stream as pdf_v2_stream


def build_job_paths(file_hash: str, target_lang: str):
    """Où vivent les artefacts d'un document : (job_dir, lang_dir).

    Le magasin est adressé par le SEUL hash du contenu : `translations/{hash}/`.
    Le nom du fichier n'entre PAS dans le chemin — `contrat.pdf` et
    `contrat-final.pdf` au contenu identique, ou le même fichier déposé par deux
    comptes, partagent donc le même dossier et ne sont traduits qu'une fois. Le
    nom d'origine est conservé par Document, pour l'affichage seulement.

    Aucun segment de VERSION de moteur : on ne conserve plus le PDF rendu (il se
    recalcule à la demande depuis l'original + la traduction, sans DeepSeek), et
    ce qui est stocké — la traduction — ne dépend pas de la géométrie du moteur.
    Rien à invalider, donc rien à versionner.

    Fonction extraite de `translate_endpoint` pour être TESTABLE : noyée dans
    l'endpoint, elle ne pouvait être vérifiée que par des tests tautologiques.
    """
    job_dir = os.path.join(TRANSLATIONS_DIR, file_hash)
    lang_dir = os.path.join(job_dir, target_lang)
    return job_dir, lang_dir

def cap_pages_for_plan(pages_set, ext: str, page_limit: int):
    """Applique la limite de pages du plan à la sélection demandée.

    Extraite de l'endpoint pour être TESTABLE — l'ancienne version, inline, ne
    forçait la page 1 que pour `ext == "pdf"` : un plan d'essai qui déposait un
    PPTX sans sélection obtenait TOUTES les diapositives traduites. La limite
    ne vaut que si elle s'applique à tout format qui sait sélectionner ses
    pages (PDF et PPTX ; le DOCX, sans notion de page à l'extraction, est
    refusé plus haut pour un plan limité).
    """
    if ext not in ("pdf", "pptx"):
        return pages_set
    if pages_set and len(pages_set) > page_limit:
        return {min(pages_set)}       # on ne garde que la 1re page demandée
    if not pages_set and page_limit == 1:
        return {1}                    # force page 1 uniquement
    return pages_set


def count_pages(file_bytes: bytes, ext: str) -> int:
    """Nombre de pages/diapositives du fichier déposé.

    Sert à FACTURER avant de traduire : sans sélection explicite, il faut bien
    savoir combien de pages on s'apprête à vendre. La lecture est bon marché
    (on ouvre le conteneur, on ne rend rien) et ne touche pas au moteur.

    En cas de doute, on renvoie 1 — jamais 0 : un fichier illisible qui
    coûterait « zéro page » serait une traduction gratuite illimitée pour qui
    sait fabriquer un en-tête invalide. Le vrai refus viendra de l'extraction,
    quelques lignes plus loin, avec un message qui parle.
    """
    try:
        if ext == "pdf":
            import fitz
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                return max(1, doc.page_count)
        if ext == "pptx":
            import io as _io
            from pptx import Presentation
            return max(1, len(Presentation(_io.BytesIO(file_bytes)).slides))
    except Exception:
        logger.warning("Comptage de pages impossible (%s) — facturé 1 page.", ext)
    return 1


docx_engine = DOCXTranslatorEngine()

# Le moteur PPTX n'est PAS un singleton : chaque opération (job de traduction,
# rendu à la demande) crée le sien. Voir la docstring de PPTXTranslatorEngine —
# une instance partagée faisait se recouvrir les dossiers temporaires de deux
# traitements simultanés, et l'aperçu d'une langue rendait celui d'une autre.
# On ne garde ici que la DISPONIBILITÉ du moteur.
pptx_available = PPTXTranslatorEngine is not None


def new_pptx_engine():
    """Un moteur PPTX neuf, à usage unique. None si le moteur est indisponible."""
    if PPTXTranslatorEngine is None:
        return None
    try:
        return PPTXTranslatorEngine()
    except Exception:
        return None

try:
    ai_translator = TranslatorAI()
    ai_active = True
except Exception as e:
    ai_active = False
    _STARTUP_NOTES.append((logging.WARNING, f"IA non initialisée : {e}"))

_ready = ["PDF v2 progressif (page par page)", "DOCX"]
if pptx_available:
    _ready.append("PPTX")
if ai_active:
    _ready.append("IA")
if limiter:
    _ready.append("rate-limit")
_STARTUP_NOTES.append((logging.INFO, "Moteurs     ~  " + " · ".join(_ready)))

# ── Pré-chauffage LibreOffice ────────────────────────────────────────────────
# Le premier appel à LibreOffice prend 3-5s (démarrage à froid). On lance un
# appel factice en arrière-plan pour que le processus soit chaud quand la
# première conversion réelle arrivera.
def _prewarm_soffice():
    if not SOFFICE_PATH:
        return
    try:
        import tempfile as _tf, subprocess as _sp
        # Voir `convert_to_pdf_bytes` : le profil reste verrouillé un instant.
        # Ici le nettoyage a lieu dans un thread démon, et son échec était
        # signalé au tout dernier moment — d'où le `PermissionError` affiché
        # APRÈS le score vert d'une suite de tests.
        with _tf.TemporaryDirectory(ignore_cleanup_errors=True) as _td:
            src = os.path.join(_td, "warm.docx")
            # Fichier DOCX minimal pour que LibreOffice ait quelque chose à ouvrir
            with open(src, "wb") as _f:
                _f.write(b"PK\x03\x04" + b"\x00" * 22)  # en-tête ZIP minimal
            profile = "file:///" + os.path.join(_td, "prof").replace(os.sep, "/")
            _sp.run([SOFFICE_PATH, "--headless", "--norestore", "--nolockcheck",
                     f"-env:UserInstallation={profile}",
                     "--convert-to", "pdf", "--outdir", _td, src],
                    capture_output=True, timeout=30)
    except Exception:
        pass  # échec silencieux : la première conversion sera juste plus lente

import threading as _th
_th.Thread(target=_prewarm_soffice, daemon=True).start()

# Deux modes de traduction, choisis par requête via le paramètre `quality` :
#  • "fast"    → modèle non-raisonnant, ~secondes/page, version stable (défaut) ;
#  • "precise" → modèle à raisonnement, alignement id↔texte fiable sur les pages
#                complexes (numéros + formules), mais ~1-2 min/page.
# Noms surchargeables via .env si DeepSeek renomme ses modèles.
# `deepseek-chat` était un ALIAS de compatibilité vers `deepseek-v4-flash` en
# mode non-raisonnant, supprimé par DeepSeek le 24/07/2026 à 15:59 UTC. On vise
# donc le modèle réel : à cette date, le comportement est identique — c'est le
# même modèle — mais le nom, lui, survivra.
FAST_MODEL = os.getenv("DEEPSEEK_MODEL_FAST", "deepseek-v4-flash")
PRECISE_MODEL = os.getenv("DEEPSEEK_MODEL_PRECISE", "deepseek-v4-flash")

def _resolve_quality(quality: str):
    """(model, max_tokens) selon le mode demandé. Le mode précis a besoin d'un
    gros budget de tokens car le raisonnement en consomme avant la réponse."""
    if quality == "precise":
        return PRECISE_MODEL, 65536
    return FAST_MODEL, 8192


# ── Job manager ──────────────────────────────────────────────────────────────
# Chaque job de traduction est identifié par un UUID. Il possède :
#   - une queue thread-safe pour les messages de progression
#   - un état (pending / running / done / error)
#   - le chemin du fichier résultat une fois terminé
# Les jobs sont nettoyés automatiquement après 30 minutes.

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

# Un job terminé reste consultable (partiel/résultat) pendant cette durée, puis
# est oublié et son PDF partiel effacé. Le commentaire d'origine promettait ce
# ménage (« nettoyés après 30 minutes ») mais RIEN ne l'implémentait : les jobs
# s'accumulaient en mémoire et les partial_*.pdf sur le disque, sans borne.
JOB_RETENTION_SECONDS = 30 * 60
# Un job encore « en vie » au-delà de cette durée a perdu son worker (plantage
# sans _job_error) : on l'oublie aussi.
JOB_MAX_AGE_SECONDS = 24 * 3600

def _gc_jobs() -> None:
    """Oublie les jobs finis depuis > 30 min et efface leurs fichiers
    TRANSITOIRES (PDF partiel + rendu). La traduction persistante (pages.json)
    n'est jamais touchée ici : elle vit dans le magasin, protégée par la purge
    par références."""
    now = time.time()
    with _jobs_lock:
        morts = [
            (jid, j) for jid, j in _jobs.items()
            if (j.get("finished_at") and now - j["finished_at"] > JOB_RETENTION_SECONDS)
            or (now - j.get("created_at", now) > JOB_MAX_AGE_SECONDS)
        ]
        for jid, _ in morts:
            del _jobs[jid]
    for _, j in morts:
        for f in (j.get("partial_path"), j.get("result_path")):
            if f and os.path.isfile(f):
                try:
                    os.remove(f)
                except OSError:
                    pass

def _new_job() -> str:
    _gc_jobs()
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "state": "pending",
            "created_at": time.time(),
            "q": queue.Queue(),
            "result_path": None,
            "result_filename": None,
            "partial_path": None,     # PDF v2 : fichier partiel (pages prêtes)
            "error": None,
            # PROPRIÉTAIRE du job. Sans lui, un job_id deviné suffisait à
            # récupérer le document d'autrui : /partial et /result ne
            # vérifiaient que la clé d'API, laquelle est publique (elle est
            # dans le bundle du frontend).
            "user_id": None,
        }
    return job_id

# Intervalle minimal entre deux écritures d'avancement en base.
_PROGRESS_EVERY_S = 3.0


def _job_emit(job_id: str, event_type: str, payload: dict):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job:
        job["q"].put({"type": event_type, **payload})

def _sync_document_progress(job_id: str, done: int, total: int | None = None):
    """Consigne l'avancement en base, pour qu'il survive à la session.

    ÉCRITURE LIMITÉE. Un document de 285 pages ferait 285 transactions, chacune
    ouvrant sa propre connexion (voir `_sync_document_status` : on est dans un
    thread worker, le pool principal n'est pas utilisable). On n'écrit donc que
    toutes les `_PROGRESS_EVERY_S` secondes — sauf la DERNIÈRE page, qu'on
    écrit toujours : c'est celle qui fait passer la barre à 100 %, et la sauter
    laisserait un document terminé affiché à 97 %.
    """
    with _jobs_lock:
        job = _jobs.get(job_id)
        doc_id = job.get("document_id") if job else None
        if not doc_id:
            return
        derniere = total is not None and done >= total
        if not derniere:
            precedent = job.get("_progress_at", 0.0)
            if time.time() - precedent < _PROGRESS_EVERY_S:
                return
        job["_progress_at"] = time.time()

    async def _update():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.pool import NullPool
        from database import DATABASE_URL
        from models import Document as _D
        eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with AsyncSession(eng) as db:
                doc = await db.get(_D, doc_id)
                if doc is None:
                    return
                doc.pages_done = done
                if total and not doc.page_count:
                    doc.page_count = total
                await db.commit()
        finally:
            await eng.dispose()
    try:
        import asyncio as _aio
        _aio.run(_update())
    except Exception as e:
        # L'avancement est un CONFORT : son échec ne doit jamais interrompre
        # une traduction en cours, qui elle a de la valeur. Mais il doit se
        # VOIR — un `except: pass` muet a déjà coûté une heure de recherche
        # ici même : la barre restait à zéro sans que rien ne le signale.
        # `_aio.run` échoue notamment si on l'appelle depuis une boucle déjà
        # en cours ; ce chemin n'est légitime que depuis un thread worker.
        logger.warning("Avancement non consigné (doc %s, %s pages) : %s",
                       doc_id, done, e)


def _sync_document_status(job_id: str, status: str, translated_path: str | None = None):
    """Reporte l'état d'un job sur le Document en base (si l'utilisateur était
    connecté). Appelé depuis un THREAD worker (hors boucle asyncio) → on ouvre
    une boucle jetable via `asyncio.run`. Sans ce report, le Document restait
    éternellement `translating` et `translated_path` NULL : le téléchargement
    servait alors l'ORIGINAL au lieu de la traduction."""
    with _jobs_lock:
        job = _jobs.get(job_id)
        doc_id = job.get("document_id") if job else None
    if not doc_id:
        return

    async def _update():
        # Moteur DÉDIÉ à connexion NON poolée : on tourne dans une boucle jetable
        # (thread worker), or le pool du moteur global est lié à la boucle
        # principale d'uvicorn — y réutiliser une connexion lèverait « Event loop
        # is closed ». NullPool ouvre une connexion neuve sur CETTE boucle et la
        # ferme avec le moteur.
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.pool import NullPool
        from database import DATABASE_URL
        from models import Document as _D
        eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
        try:
            async with AsyncSession(eng) as db:
                doc = await db.get(_D, doc_id)
                if doc is None:
                    return
                doc.status = status
                if translated_path:
                    doc.translated_path = translated_path
                await db.commit()
        finally:
            await eng.dispose()
    try:
        import asyncio as _aio
        _aio.run(_update())
    except Exception:
        pass

def _job_done(job_id: str, result_path: str, filename: str,
              translation_path: str | None = None):
    """`result_path` = le rendu (transitoire) que /result sert tout de suite.
    `translation_path` = la traduction PERSISTANTE (pages.json/translated.json)
    consignée en base : c'est elle qui permet de recalculer le rendu plus tard,
    pas le fichier transitoire. Faute de quoi `Document.translated_path`
    pointerait sur un rendu que le GC efface au bout de 30 min."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job:
        job["result_path"] = result_path
        job["result_filename"] = filename
        job["state"] = "done"
        job["finished_at"] = time.time()
        job["q"].put({"type": "done", "filename": filename})
    _sync_document_status(job_id, "done",
                          translated_path=translation_path or result_path)

def _job_error(job_id: str, message: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job:
        job["error"] = message
        job["state"] = "error"
        job["finished_at"] = time.time()
        job["q"].put({"type": "error", "message": message})
    _sync_document_status(job_id, "error")

def _make_progress_cb(job_id: str, step: str, total: int | None = None):
    """Retourne un progress_callback lié à un job et à une étape."""
    counter = [0]
    def cb(msg: str):
        # Détecter le pattern "page X/N" pour afficher la progression fine
        page, tot = None, total
        import re
        m = re.search(r'(\d+)/(\d+)', msg)
        if m:
            page, tot = int(m.group(1)), int(m.group(2))
            counter[0] = page
        _job_emit(job_id, "progress", {
            "step": step,
            "message": msg,
            "page": page or counter[0],
            "total": tot,
        })
        logger.info(msg)
    return cb

def _run_translation_job(
    job_id: str, file_bytes: bytes, filename: str, ext: str,
    target_lang: str, format_opts: dict,
    job_dir: str, lang_dir: str, original_path: str,
    extraction_path: str, translated_path: str,
    output_path: str, output_filename: str,
    model: str, max_tokens: int, pages_set=None, debug: bool = False,
):
    """Exécute toute la pipeline dans un thread de fond et émet des events SSE.

    `translated_path` (translated.json) est la traduction PERSISTANTE ; le rendu
    `output_path` est transitoire. Un document déjà traduit relit ce JSON et se
    contente de ré-injecter (aucun appel DeepSeek)."""
    # Moteur PPTX PROPRE à ce job : son dossier temporaire ne doit être partagé
    # avec aucun autre traitement (cf. PPTXTranslatorEngine).
    pptx_eng = new_pptx_engine() if ext == "pptx" else None
    try:
        _job_emit(job_id, "progress", {"step": "start", "message": "Démarrage du job...", "page": 0, "total": None})

        # 2. Sauvegarde de l'original
        if not os.path.exists(original_path):
            with open(original_path, "wb") as f:
                f.write(file_bytes)

        # 3. Extraction
        if not os.path.exists(extraction_path):
            cb_extract = _make_progress_cb(job_id, "extract")
            _job_emit(job_id, "progress", {"step": "extract", "message": "Extraction du texte...", "page": 0, "total": None})
            extraction = None
            if ext == "docx":
                filters = {"paragraphs": True, "tables": True, "headers_footers": True, "text_boxes": True, "smartarts": True}
                extraction, _ = docx_engine.extract_text(original_path, extraction_path, filters=filters, progress_callback=cb_extract)
            elif ext == "pptx" and pptx_eng:
                filters = {"shapes": True, "smartarts": True, "tables": True, "connectors": True}
                extraction, _ = pptx_eng.extract_text(original_path, extraction_path, filters=filters, progress_callback=cb_extract, pages=pages_set)
            else:
                raise ValueError(f"Type de fichier .{ext} non supporté.")
            if not extraction:
                if os.path.exists(extraction_path):
                    os.remove(extraction_path)
                raise ValueError("Échec de l'extraction du texte.")
        else:
            _job_emit(job_id, "progress", {"step": "extract", "message": "Extraction : cache utilisé.", "page": 0, "total": None})

        # 4. Traduction IA — ou IDENTITÉ en mode structure/debug
        if debug:
            # Aucune traduction : translated_text = texte d'origine, comme
            # test_extract_inject.py. Le rendu (étape 5) ajoute les bordures.
            if not os.path.exists(translated_path):
                _job_emit(job_id, "progress", {"step": "translate", "message": "Mode structure : copie identité (sans traduction).", "page": 0, "total": None})
                with open(extraction_path, "r", encoding="utf-8") as f:
                    _ext = json.load(f)
                for _pg in _ext.get("pages", []):
                    for _b in _pg.get("text_blocks", []):
                        _b["translated_text"] = _b.get("text", "")
                with open(translated_path, "w", encoding="utf-8") as f:
                    json.dump(_ext, f, ensure_ascii=False)
            else:
                _job_emit(job_id, "progress", {"step": "translate", "message": "Mode structure : cache utilisé.", "page": 0, "total": None})
        elif not os.path.exists(translated_path):
            if not ai_active:
                raise ValueError("Le traducteur IA n'est pas disponible.")
            cb_translate = _make_progress_cb(job_id, "translate")
            _job_emit(job_id, "progress", {"step": "translate", "message": "Traduction IA en cours...", "page": 0, "total": None})
            success, result = ai_translator.translate_json(extraction_path, target_lang=target_lang, progress_callback=cb_translate, model=model, max_tokens=max_tokens)
            if not success:
                raise ValueError(f"Traduction échouée : {result}")
            if os.path.exists(result) and os.path.abspath(result) != os.path.abspath(translated_path):
                shutil.move(result, translated_path)
        else:
            _job_emit(job_id, "progress", {"step": "translate", "message": "Traduction : cache utilisé.", "page": 0, "total": None})

        # 5. Injection / génération (DOCX/PPTX — le PDF passe par le moteur v2).
        _job_emit(job_id, "progress", {"step": "inject", "message": "Génération du document traduit...", "page": 0, "total": None})
        if ext == "docx":
            inj_ok, inj_msg = docx_engine.inject_translation(original_path, translated_path, output_path, format_options=format_opts)
        elif ext == "pptx" and pptx_eng:
            inj_ok, inj_msg = pptx_eng.inject_translation(original_path, translated_path, output_path, format_options=format_opts)
            if inj_ok:
                pptm_auto_path = output_path[:-5] + "_autorefresh.pptm" if output_path.endswith(".pptx") else output_path + "_autorefresh.pptm"
                pptx_eng.generate_autorefresh_pptm(output_path, pptm_auto_path)
        else:
            raise ValueError("Type de fichier non supporté pour la génération.")

        if not inj_ok:
            if os.path.exists(output_path):
                os.remove(output_path)
            raise ValueError(f"Injection échouée : {inj_msg}")

        if not os.path.exists(output_path):
            raise ValueError("Le fichier traduit est introuvable après génération.")

        _job_done(job_id, output_path, output_filename,
                  translation_path=translated_path)

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        _job_error(job_id, "La traduction a rencontré une erreur. Réessayez ou contactez le support.")


def _elements_de(slide_data: dict):
    """Tous les fragments traduisibles d'une slide, à plat.

    Le même parcours était recopié à chaque usage (construction de la carte de
    réinjection, mode debug, contrôles) : cinq copies à tenir d'accord, et une
    famille oubliée quelque part passait inaperçue.
    """
    yield from slide_data.get("text_elements", [])
    for groupe in ("diagram_elements", "chart_elements", "layout_elements"):
        for bloc in slide_data.get(groupe, []):
            yield from bloc.get("text_elements", [])
    yield from slide_data.get("excel_elements", [])


# ── Cohérence terminologique du DOCUMENT ─────────────────────────────────────
#
# Un même mot source doit recevoir la même traduction d'un bout à l'autre d'un
# document. Le modèle traduit slide par slide et n'a aucune mémoire d'une slide
# à l'autre : il a rendu « Gerbeur » par « Stacker » quinze fois, et l'a laissé
# en français une seizième (mesuré, slide 17). Aucune règle de FORME ne peut
# l'attraper — le fragment est parfaitement bien balisé.
#
# La preuve vient du document lui-même (cf. runtags.termes_incoherents), jamais
# d'une liste de termes. Reste que les COGNATS (« motivation », « progression »)
# y ressemblent à s'y méprendre : la consigne ci-dessous est donc écrite pour
# qu'un cognat reste INCHANGÉ sans dommage, et pour que la reprise ne touche
# QUE le terme — pas le reste d'une phrase déjà correcte.

_CONSIGNE_COHERENCE = (
    "COHÉRENCE DU DOCUMENT. Dans ta traduction ci-dessous, ces termes sont "
    "restés identiques à la source : {termes}. Ailleurs dans le MÊME document, "
    "tu les as traduits. Reprends ta traduction en ne changeant QUE ce qui "
    "concerne ces termes — garde le reste MOT POUR MOT.\n"
    "Si l'un d'eux s'écrit de la même façon dans la langue cible, ou s'il "
    "s'agit d'un nom propre, d'une marque ou d'un sigle, LAISSE-LE TEL QUEL : "
    "c'est légitime, et le changer serait une faute.\n"
    "Ta traduction précédente : {precedente}"
)


def _coherence_document(slides_traduites: dict, pptx_eng, target_lang: str,
                        progress_cb=None) -> int:
    """Reprend les fragments qui laissent en langue source un terme que le
    document traduit ailleurs. Renvoie le nombre de fragments repris.

    Best-effort : toute erreur laisse la traduction en l'état. Une passe de
    confort ne doit jamais faire échouer un travail déjà abouti.
    """
    fragments = [(sn, el) for sn, sd in slides_traduites.items()
                 for el in _elements_de(sd) if el.get("translated_text")]
    if not fragments:
        return 0

    incoherents = runtags.termes_incoherents(
        (el["text"], el["translated_text"]) for _sn, el in fragments)
    if not incoherents:
        return 0

    a_reprendre, slides_touchees = [], set()
    for sn, el in fragments:
        termes = runtags.termes_a_reprendre(el["text"], el["translated_text"],
                                            incoherents)
        if not termes:
            continue
        el["consigne"] = _CONSIGNE_COHERENCE.format(
            termes=", ".join(termes), precedente=el["translated_text"])
        a_reprendre.append(el)
        slides_touchees.add(sn)
    if not a_reprendre:
        return 0

    if progress_cb:
        progress_cb(f"cohérence : {len(a_reprendre)} fragment(s) repris "
                    f"({len(incoherents)} terme(s) concerné(s)).")
    # `_translate_batch` écrit `translated_text` DANS ces dictionnaires, qui
    # sont ceux de `slides_traduites` : la correction se propage donc au JSON
    # persistant sans qu'on ait à le reconstruire.
    ai_translator._translate_batch(a_reprendre, target_lang, progress_cb,
                                   passes=0)
    for el in a_reprendre:
        el.pop("consigne", None)

    # Réinjection des seules slides touchées. L'injection écrit par
    # identifiant de paragraphe : la repasser sur un XML déjà injecté remplace
    # simplement le texte des runs, sans avoir besoin de la source.
    for sn in sorted(slides_touchees):
        sd = slides_traduites.get(sn)
        if sd:
            pptx_eng.inject_slide(sn, {
                el["id"]: (el.get("translated_text") or el["text"])
                for el in _elements_de(sd)})
    return len(a_reprendre)


def _run_pptx_progressive_job(
    job_id: str, file_bytes: bytes, original_path: str,
    output_path: str, output_filename: str, partial_path: str,
    translation_path: str, target_lang: str,
    pages_set=None, debug: bool = False, is_admin: bool = False,
):
    """Pipeline PPTX PROGRESSIF : extraction, traduction et réinjection SLIDE
    PAR SLIDE. Le PPTX partiel est construit puis converti en PDF pour être
    servi via /api/translate/partial/{job_id}. Événements SSE comme le PDF v2.

    Optimisation ADMIN : si is_admin=True, traduit 5 slides en parallèle (5 workers)
    pour diviser le temps de traitement PPTX par 5."""
    # Moteur PROPRE à ce job. Il était partagé avec les aperçus : le
    # `_cleanup_temp()` d'un aperçu ouvert pendant la traduction supprimait le
    # dossier temporaire SOUS le job (cf. PPTXTranslatorEngine).
    pptx_eng = new_pptx_engine()
    try:
        if not pptx_eng:
            raise ValueError("Moteur PPTX indisponible.")

        # ── Sauvegarde de l'original ──────────────────────────────────────
        if not os.path.exists(original_path):
            with open(original_path, "wb") as f:
                f.write(file_bytes)

        # ── Décompression ─────────────────────────────────────────────────
        _job_emit(job_id, "progress", {"step": "extract", "message": "Décompression du PPTX...", "page": 0, "total": None})
        pptx_eng._extract_zip(original_path)
        total_slides = pptx_eng.slide_count()

        if not total_slides:
            raise ValueError("Aucune slide trouvée dans le PPTX.")

        # Appliquer la sélection de pages
        if pages_set:
            slides_to_process = sorted(s for s in pages_set if 1 <= s <= total_slides)
            if not slides_to_process:
                slides_to_process = [1]
        else:
            slides_to_process = list(range(1, total_slides + 1))

        total = len(slides_to_process)
        _job_emit(job_id, "start", {"total": total})

        # Enregistrer le partial_path dans le job pour que /partial le trouve.
        with _jobs_lock:
            job = _jobs.get(job_id)
            if job is not None:
                job["partial_path"] = partial_path

        # ── Filtres d'extraction ──────────────────────────────────────────
        filters = {"shapes": True, "smartarts": True, "tables": True, "connectors": True}

        # ── Traduction PROGRESSIVE slide par slide ─────────────────────────
        done = 0
        done_lock = threading.Lock()
        max_workers = 5 if is_admin else 1
        # Slide -> son extraction AVEC sa traduction, retenue avant injection.
        # C'est ce qui devient `translated.json` (cf. plus bas).
        slides_traduites: dict[int, dict] = {}

        # ── Aperçu PROGRESSIF : un convertisseur de partiel en arrière-plan ──
        # Après chaque slide traitée on veut montrer l'avant/après SANS attendre
        # la fin du document (comme le PDF v2). La conversion PPTX→PDF passe par
        # LibreOffice, qui coûte plusieurs secondes et ne s'appelle pas en
        # parallèle : on la confie à UN thread dédié qui, à tout instant, ne rend
        # QUE le plus haut numéro de slide prêt (coalescence). Si la traduction
        # va plus vite que la conversion, on saute les états intermédiaires — le
        # lecteur voit toujours le partiel le plus récent, jamais une file qui
        # s'accumule.
        #
        # ON CONVERTIT LE DECK ENTIER, PAS SLIDE À SLIDE — c'est contre-intuitif,
        # et j'ai fait l'erreur inverse. Le raisonnement « à la slide 30 on
        # re-rend 30 slides, donc c'est en n² » suppose que le coût suit le
        # nombre de slides. MESURÉ, il ne le suit pas :
        #
        #     PPTX minimal, 1 slide, 27 Ko ......  7,05 s   ← plancher
        #     1 slide extraite d'un deck de 13 Mo  11,06 s
        #     les 26 slides du même deck .......   16,59 s
        #
        # Le coût est celui du DÉMARRAGE de LibreOffice, pas du rendu. Et une
        # slide isolée pèse presque autant que le deck (95 % du poids est dans
        # les médias, qu'on ne peut pas retirer). Convertir slide par slide
        # revenait donc à 26 × 11 s = 288 s là où le deck entier coûte 17 s :
        # dix-sept fois plus lent, et le verrou LibreOffice monopolisé pendant
        # toute la traduction — ce qui affamait AUSSI la conversion du panneau
        # source, resté vide à l'écran.
        #
        # La coalescence est donc la bonne réponse, et la seule : un partiel
        # toutes les ~17 s, toujours le plus récent.
        #
        # Réservé au mode SÉQUENTIEL : en parallèle (admin), le dossier
        # temporaire est muté par plusieurs slides à la fois et un partiel lu au
        # vol serait incohérent. L'admin échange l'aperçu progressif contre la
        # vitesse (il verra le partiel final, comme avant).
        _progressive = (max_workers == 1)
        _partial_cv = threading.Condition()
        _partial_target = [0]           # plus haut slide prêt à rendre (0 = rien)
        _partial_stop = [False]

        def _write_pptx_pdf_partial(up_to: int):
            """Construit le PPTX partiel (1..up_to), le convertit en PDF et
            l'écrit ATOMIQUEMENT dans partial_path — c'est ce PDF que /partial
            sert (rastérisé et filigrané pour un plan d'essai)."""
            with tempfile.TemporaryDirectory() as td:
                ppx = os.path.join(td, "partial.pptx")
                pptx_eng.build_partial_pptx(ppx, up_to)
                with open(ppx, "rb") as f:
                    pptx_bytes = f.read()
            pdf_bytes = convert_to_pdf_bytes(pptx_bytes, "pptx", use_cache=False)
            tmp = partial_path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(pdf_bytes)
            os.replace(tmp, partial_path)

        def _partial_worker():
            while True:
                with _partial_cv:
                    while _partial_target[0] == 0 and not _partial_stop[0]:
                        _partial_cv.wait()
                    if _partial_stop[0] and _partial_target[0] == 0:
                        return
                    up_to = _partial_target[0]
                    _partial_target[0] = 0
                try:
                    _write_pptx_pdf_partial(up_to)
                except Exception as e:
                    # Best-effort : un partiel manqué n'interrompt jamais la
                    # traduction ; le prochain slide en produira un plus récent.
                    logger.warning("Partiel PPTX (jusqu'à slide %s) non généré : %s",
                                   up_to, e)

        def _request_partial(up_to: int):
            if not _progressive:
                return
            with _partial_cv:
                if up_to > _partial_target[0]:
                    _partial_target[0] = up_to
                _partial_cv.notify()

        _partial_thread = None
        if _progressive:
            _partial_thread = threading.Thread(
                target=_partial_worker, daemon=True,
                name=f"pptx-partial-{job_id[:8]}")
            _partial_thread.start()

        def _process_one_slide(slide_num: int):
            nonlocal done
            _job_emit(job_id, "page", {"page": slide_num, "status": "extracting",
                         "done": done, "total": total})
            _sync_document_progress(job_id, done, total)
            slide_data, info = pptx_eng.extract_slide(slide_num, filters)
            if not slide_data:
                with done_lock:
                    done += 1
                    cur_done = done
                _job_emit(job_id, "page", {"page": slide_num, "status": "copied",
                             "done": cur_done, "total": total})
                _sync_document_progress(job_id, cur_done, total)
                _request_partial(slide_num)
                return

            _job_emit(job_id, "page", {"page": slide_num, "status": "translating",
                         "done": done, "total": total})
            _sync_document_progress(job_id, done, total)

            if debug:
                for el in slide_data.get("text_elements", []):
                    el["translated_text"] = el["text"]
                for diag in slide_data.get("diagram_elements", []):
                    for el in diag.get("text_elements", []):
                        el["translated_text"] = el["text"]
                for chart in slide_data.get("chart_elements", []):
                    for el in chart.get("text_elements", []):
                        el["translated_text"] = el["text"]
                for layout in slide_data.get("layout_elements", []):
                    for el in layout.get("text_elements", []):
                        el["translated_text"] = el["text"]
                for el in slide_data.get("excel_elements", []):
                    el["translated_text"] = el["text"]
            else:
                if not ai_active:
                    raise ValueError("Le traducteur IA n'est pas disponible.")
                mini_json = os.path.join(
                    pptx_eng._get_temp_dir(), f"_slide{slide_num}.json")
                with open(mini_json, "w", encoding="utf-8") as f:
                    json.dump({"slides": [slide_data]}, f, ensure_ascii=False)

                success, result = ai_translator.translate_json(
                    mini_json, target_lang=target_lang,
                    progress_callback=_make_progress_cb(job_id, "translate"),
                )
                if not success:
                    raise ValueError(f"Traduction slide {slide_num} échouée : {result}")

                with open(result, "r", encoding="utf-8") as f:
                    translated = json.load(f)
                if translated.get("slides"):
                    slide_data = translated["slides"][0]
                for p in (mini_json, result):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

            _job_emit(job_id, "page", {"page": slide_num, "status": "rendering",
                         "done": done, "total": total})
            _sync_document_progress(job_id, done, total)

            tmap = {el["id"]: (el.get("translated_text") or el["text"])
                    for el in _elements_de(slide_data)}

            # La traduction PERSISTANTE se retient ICI, AVANT l'injection —
            # c'est le seul moment où l'on tient encore la SOURCE et la CIBLE
            # côte à côte. Elle était reconstituée à la fin en ré-extrayant les
            # XML DÉJÀ INJECTÉS : `text` y contenait la traduction et
            # `translated_text` valait None. Le document perdait donc sa source,
            # le rendu à la demande resservait une traduction prise pour un
            # original, et aucune vérification ultérieure n'avait plus de quoi
            # comparer.
            with done_lock:
                slides_traduites[slide_num] = slide_data

            pptx_eng.inject_slide(slide_num, tmap)

            with done_lock:
                done += 1
                cur_done = done

            _job_emit(job_id, "page", {"page": slide_num, "status": "done",
                         "done": cur_done, "total": total})
            _sync_document_progress(job_id, cur_done, total)
            _request_partial(slide_num)

        if max_workers > 1:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_process_one_slide, sn) for sn in slides_to_process]
                for f in futures:
                    f.result()
        else:
            for sn in slides_to_process:
                _process_one_slide(sn)

        # Arrêter le convertisseur de partiel AVANT de bâtir le fichier final :
        # plus aucun accès concurrent au dossier temporaire pendant que le PPTX
        # final se construit et que le temp dir est nettoyé.
        if _partial_thread is not None:
            with _partial_cv:
                _partial_stop[0] = True
                _partial_cv.notify()
            _partial_thread.join(timeout=130)

        # ── Cohérence terminologique, une fois TOUT le document connu ──────
        # Elle ne peut pas se faire plus tôt : la preuve qu'un terme est
        # traduisible vient des AUTRES slides. Après l'arrêt du convertisseur
        # de partiel, donc sans accès concurrent au dossier temporaire.
        if not debug and ai_active:
            try:
                _job_emit(job_id, "progress", {"step": "coherence", "message": "Contrôle de cohérence des termes...", "page": 0, "total": None})
                n_coh = _coherence_document(
                    slides_traduites, pptx_eng, target_lang,
                    _make_progress_cb(job_id, "coherence"))
                if n_coh:
                    logger.info(f"Job {job_id}: {n_coh} fragment(s) repris "
                                f"pour cohérence terminologique")
            except Exception as e:
                logger.warning(f"Job {job_id}: contrôle de cohérence ignoré : {e}")

        # ── Aperçus OLE Excel : régénérés depuis les classeurs traduits ────
        # Pour que le fichier téléchargé (et l'aperçu final) montre les
        # tableaux/graphiques Excel EN LANGUE CIBLE sans devoir activer l'objet
        # dans PowerPoint. Best-effort : un échec n'interrompt pas la traduction.
        try:
            _job_emit(job_id, "progress", {"step": "ole", "message": "Régénération des aperçus Excel...", "page": 0, "total": None})
            n_ole = pptx_eng.regenerate_ole_previews(soffice_path=SOFFICE_PATH)
            if n_ole:
                logger.info(f"Job {job_id}: {n_ole} aperçu(s) OLE Excel régénéré(s)")
        except Exception as e:
            logger.warning(f"Job {job_id}: régénération OLE ignorée : {e}")

        # ── PPTX final ────────────────────────────────────────────────────
        _job_emit(job_id, "progress", {"step": "inject", "message": "Génération du PPTX final...", "page": 0, "total": None})
        pptx_eng.build_partial_pptx(output_path, max(slides_to_process))

        # ── Sauvegarde de la traduction (JSON complet pour reprise) ───────
        # Assemblée depuis ce qu'on a retenu AVANT injection : `text` y est la
        # SOURCE et `translated_text` la traduction. Ré-extraire les XML ici
        # revenait à relire notre propre sortie et à la déclarer originale.
        full_json = {"slides": [slides_traduites[sn]
                                for sn in slides_to_process
                                if sn in slides_traduites]}
        with open(translation_path, "w", encoding="utf-8") as f:
            json.dump(full_json, f, ensure_ascii=False)

        pptx_eng._cleanup_temp()
        _job_done(job_id, output_path, output_filename,
                  translation_path=translation_path)

    except Exception as e:
        logger.error(f"Job PPTX {job_id} failed: {e}")
        # Réveiller le convertisseur de partiel pour qu'il s'arrête (sinon il
        # attend indéfiniment sur sa condition).
        try:
            with _partial_cv:
                _partial_stop[0] = True
                _partial_cv.notify()
        except Exception:
            pass
        try:
            pptx_eng._cleanup_temp()
        except Exception:
            pass
        _job_error(job_id, "La traduction a rencontré une erreur. Réessayez ou contactez le support.")


def _run_pdf_v2_job(
    job_id: str, file_bytes: bytes, original_path: str,
    output_path: str, output_filename: str, partial_path: str,
    translation_path: str, target_lang: str, pages_set=None, debug: bool = False,
):
    """Pipeline PDF v2 PROGRESSIF : chaque page est extraite, traduite et rendue
    avant la suivante. Le PDF partiel grandit page après page — le client
    l'affiche au fil de l'eau via /api/translate/partial/{job_id}. Événements
    SSE émis : start{total} puis page{page,status,done,total}.

    `translation_path` (pages.json) est la traduction PERSISTANTE : le moteur y
    relit les pages déjà traduites au lieu de rappeler DeepSeek. Un document
    déjà traité n'y déclenche donc aucun appel — il se contente d'un rendu."""
    try:
        _job_emit(job_id, "progress", {"step": "start", "message": "Démarrage du job...", "page": 0, "total": None})

        if not os.path.exists(original_path):
            with open(original_path, "wb") as f:
                f.write(file_bytes)

        with _jobs_lock:
            job = _jobs.get(job_id)
            if job is not None:
                job["partial_path"] = partial_path

        def on_event(ev: dict):
            et = ev.get("type")
            if et == "start":
                _job_emit(job_id, "start", {"total": ev.get("total")})
            elif et == "page":
                _job_emit(job_id, "page", {
                    "page": ev.get("page"),
                    "status": ev.get("status"),
                    "done": ev.get("done"),
                    "total": ev.get("total"),
                })
                # Même avancement, mais PERSISTÉ : c'est lui qui permet à une
                # autre session — ou à la même après reconnexion — de savoir
                # que le document avance encore. Les événements ci-dessus ne
                # vivent que le temps du flux SSE de celui qui l'a lancé.
                _sync_document_progress(job_id, ev.get("done") or 0,
                                        ev.get("total"))
                # Compatibilité barre de progression générique.
                _job_emit(job_id, "progress", {
                    "step": "translate",
                    "message": f"Page {ev.get('page')}/{ev.get('total')} : {ev.get('status')}",
                    "page": ev.get("done"),
                    "total": ev.get("total"),
                })

        pdf_v2_stream.translate_pdf_progressive(
            original_path, output_path, target_lang=target_lang,
            pages=pages_set, partial_path=partial_path, on_event=on_event,
            debug=debug, cache_path=translation_path,
        )

        if not os.path.exists(output_path):
            raise ValueError("Le fichier traduit est introuvable après génération.")

        # Le rendu complet vient d'être produit — on le CONSERVE au lieu de le
        # laisser au GC des transitoires. C'est lui qui rend l'aperçu et le
        # téléchargement instantanés ensuite (mesuré : 280 s à reconstruire
        # sur 285 pages). Seule la sortie CANONIQUE est conservée : un rendu
        # de débogage ou remis en page ne doit jamais être resservi comme la
        # traduction fidèle.
        if not debug and "_STRUCTURE" not in output_filename \
                and output_filename.endswith(".pdf") \
                and "_TRADUIT." in output_filename:
            try:
                with open(output_path, "rb") as f:
                    render_cache.store_render(f.read(), translation_path)
            except OSError as e:
                logger.warning("Rendu du job non conservé : %s", e)

        _job_done(job_id, output_path, output_filename,
                  translation_path=translation_path)

    except Exception as e:
        logger.error(f"Job PDF v2 {job_id} failed: {e}")
        _job_error(job_id, "La traduction a rencontré une erreur. Réessayez ou contactez le support.")


def render_translation_bytes(original_path: str, translation_path: str,
                             ext: str, target_lang: str,
                             only_pages: set[int] | None = None) -> bytes:
    """Recalcule le document traduit à partir de l'original + la traduction
    stockée, SANS jamais rappeler DeepSeek. C'est le pilier du nouveau modèle :
    on ne conserve plus le rendu, on le reconstruit à la demande.

    PDF : le moteur v2 relit `pages.json` (déjà traduit) et se contente de
    rendre. On lui passe EXPLICITEMENT les pages déjà traduites — jamais None,
    qui le pousserait à traduire les pages manquantes (donc à payer l'API). Une
    page absente du JSON est simplement recopiée de l'original.
    DOCX/PPTX : ré-injection locale de `translated.json` dans l'original.
    """
    if not os.path.isfile(original_path) or not os.path.isfile(translation_path):
        raise FileNotFoundError("Original ou traduction manquant pour le rendu.")

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, f"render.{ext}")
        if ext == "pdf":
            with open(translation_path, encoding="utf-8") as f:
                prev = json.load(f)
            pages_traduites = {
                pg.get("page_num") for pg in prev.get("pages", [])
                if any(e.get("tr_tagged") for e in pg.get("elements", [])
                       if e.get("type") == "paragraph")
            }
            pages_traduites.discard(None)
            # `only_pages` restreint ce qu'on RECONSTRUIT, pas ce qu'on livre :
            # les pages écartées sont recopiées de l'original, donc la
            # pagination reste identique et le lecteur n'a rien à recalculer.
            #
            # Mesuré sur un document de 285 pages : 280 s pour tout rendre,
            # ~1 s par page. L'aperçu n'affiche QU'UNE page à la fois — en
            # reconstruire 285 pour en montrer une était le blocage.
            if only_pages is not None:
                pages_traduites &= set(only_pages)
            pdf_v2_stream.translate_pdf_progressive(
                original_path, out, target_lang=target_lang,
                pages=pages_traduites, partial_path=None, on_event=None,
                debug=False, cache_path=translation_path,
            )
        elif ext == "docx":
            ok, msg = docx_engine.inject_translation(original_path,
                                                     translation_path, out)
            if not ok:
                raise ValueError(f"Ré-injection DOCX échouée : {msg}")
        elif ext == "pptx" and pptx_available:
            # Moteur NEUF à chaque rendu. Un moteur partagé faisait se recouvrir
            # deux rendus simultanés dans le même dossier temporaire : l'aperçu
            # d'une langue ressortait dans celui d'une autre.
            ok, msg = new_pptx_engine().inject_translation(original_path,
                                                          translation_path, out)
            if not ok:
                raise ValueError(f"Ré-injection PPTX échouée : {msg}")
        else:
            raise ValueError(f"Rendu à la demande non supporté pour .{ext}")
        with open(out, "rb") as f:
            return f.read()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
@rate_limit_decorator("10/minute")
async def health_check(request: Request):
    return {"status": "healthy", "service": "Précis Translator API"}

@app.options("/api/translate")
async def translate_options():
    return JSONResponse(content={}, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-API-Key",
    })

@app.options("/api/preview/pdf")
async def preview_pdf_options():
    return JSONResponse(content={}, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-API-Key",
    })

@app.post("/api/preview/pdf")
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
    except Exception as e:
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
                                  paid: bool = False, page_count: int = 1):
    """Enregistre un Document pour l'utilisateur connecté.

    Le Document est AUSSI le registre d'usage mensuel (compteur freemium) : on
    l'insère donc pour TOUT utilisateur authentifié, plan `free` compris — sinon
    la limite « 1 page/mois » ne pourrait jamais s'appuyer sur rien (bug : un
    plan `free` a 0 Mo de stockage, l'ancien code refusait alors la création et
    le compteur restait éternellement à 0). Le stockage n'est facturé que si le
    plan en offre ET que le quota le permet ; sinon `charge = 0` (l'usage est
    tout de même journalisé)."""
    if user is None:
        return
    try:
        plan_storage = (10_737_418_240 if user.plan == "admin"
                        else get_plan_storage(user.plan))
        charge = size if plan_storage > 0 else 0
        if charge and user.storage_used + charge > plan_storage:
            charge = 0                      # quota plein : on journalise sans facturer
        doc = Document(user_id=user.id, original_name=filename, source_lang="auto",
                       target_lang=target_lang, original_path=original_path,
                       size_bytes=size, storage_charged=charge,
                       status="translating", paid=paid,
                       # Le quota mensuel SOMME cette colonne. Laissée à NULL
                       # (son ancien état), elle rendait tout quota de pages
                       # incomptable — donc invendable.
                       page_count=page_count)
        db.add(doc)
        user.storage_used += charge
        await db.commit()
        # Lien job → Document : permet à `_job_done`/`_job_error` de reporter
        # `status`/`translated_path` à la fin du traitement (thread worker).
        with _jobs_lock:
            j = _jobs.get(job_id)
            if j is not None:
                j["document_id"] = doc.id
    except Exception:
        await db.rollback()


@app.post("/api/translate")
async def translate_endpoint(
    request: Request,
    file: UploadFile = File(...),
    target_lang: str = Form("en"),
    format_options: str = Form("{}"),
    quality: str = Form("fast"),
    precise: str = Form(""),
    pages: str = Form(""),
    debug: str = Form(""),
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

    # Le flag 'precise' du frontend force le mode raisonnement (admin)
    if precise == "1":
        quality = "precise"

    filename = file.filename or ""
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Type non supporté : .{ext}")

    try:
        file_bytes = await file.read()
    except Exception as e:
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
    quality = quality if quality in ("fast", "precise") else "fast"
    model, max_tokens = _resolve_quality(quality)
    # Suffixe de cache : les deux modes produisent des résultats différents, ils
    # ne doivent JAMAIS partager le même translated.json ni le même PDF de sortie.
    qsuffix = "" if quality == "fast" else "_precise"
    if debug_mode:
        qsuffix = "_debug"   # n'écrase jamais une vraie traduction en cache

    # Sélection de pages (PDF/PPTX) : None = tout le document. Le jeton entre
    # dans toutes les clés de cache pour qu'une plage donnée ne réutilise jamais
    # le résultat d'une autre plage (ni du document entier).
    pages_set = parse_page_range(pages) if ext in ("pdf", "pptx") else None

    # ── Limite de pages selon le plan ─────────────────────────────────────
    # On est dans un endpoint ASYNC : la session `db` et l'utilisateur
    # (`optional_auth`) sont déjà résolus par FastAPI. On interroge donc la base
    # par `await` direct — l'ancien code planifiait la coroutine sur la boucle
    # qui l'exécutait puis attendait le résultat en la bloquant (deadlock →
    # timeout 3 s → repli `free`), ce qui rétrogradait tout compte payant.
    plan = current_user.plan
    limit = get_plan_page_limit(plan)
    page_limit = limit if limit is not None else 999_999

    # Un plan limité en pages n'a droit qu'aux formats où la limite est
    # APPLICABLE (PDF, PPTX : l'extraction sait sélectionner ses pages). Le
    # DOCX se traduit d'un bloc : l'autoriser ici, c'était offrir un document
    # entier — la « limite » ne limitait rien.
    if page_limit == 1 and ext not in ("pdf", "pptx"):
        raise HTTPException(
            status_code=402,
            detail="Forfait Gratuit : essai sur PDF ou PPTX uniquement. "
                   "Passez à Starter pour traduire ce format.",
        )

    # Un plan payant couvre tout ce qu'il produit ; pour le forfait Gratuit,
    # seul l'achat rend le document lisible en clair (cf. `_may_read_clear`).
    doc_is_paid = is_paid_plan(plan)

    # ── Forfait Gratuit : une traduction offerte par mois, puis à la page ─────
    #
    # Deux titres pour traduire, dans cet ordre :
    #   1. la traduction OFFERTE du mois — une page, une fois ;
    #   2. les pages ACHETÉES d'avance, débitées ici.
    #
    # Le débit a lieu AVANT de lancer quoi que ce soit : c'est la règle du
    # produit (« paiement avant même de traduire »), et c'est aussi la seule
    # façon d'éviter qu'un travail coûteux parte pour un solde déjà vide.
    if page_limit == 1:
        # Verrou pessimiste sur la ligne User : le compteur est un
        # lire-puis-écrire (COUNT ici, INSERT du Document plus bas). Sans lock,
        # deux requêtes simultanées du même compte lisaient toutes deux 0 et
        # passaient toutes deux. Le lock tient jusqu'au commit de
        # `_save_document_for_user` : la seconde requête attend, recompte, 402.
        # Il protège désormais AUSSI le solde de pages : sans lui, deux
        # traductions lancées ensemble débiteraient toutes deux le même solde.
        locked = (await db.execute(
            select(User).where(User.id == current_user.id).with_for_update()
        )).scalar_one()
        month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0)
        r = await db.execute(
            select(func.count()).select_from(Document).where(
                Document.user_id == current_user.id,
                Document.created_at >= month_start,
            )
        )
        free_used = (r.scalar() or 0) >= 1

        if not free_used:
            # La traduction offerte : une page, celle que le plan autorise.
            pages_set = cap_pages_for_plan(pages_set, ext, page_limit)
        else:
            # On facture ce qui sera RÉELLEMENT traduit : la sélection si elle
            # existe, tout le document sinon.
            needed = len(pages_set) if pages_set else count_pages(file_bytes, ext)
            if locked.page_credits < needed:
                raise HTTPException(
                    status_code=402,
                    detail=(f"Vous avez {locked.page_credits} page(s) disponible(s) "
                            f"mais ce document en nécessite {needed}. "
                            "Achetez des pages supplémentaires pour continuer."),
                )
            locked.page_credits -= needed
            # Pas de `cap_pages_for_plan` ici : ces pages sont payées, les
            # plafonner à une seule reviendrait à encaisser sans livrer.
            #
            # Et le document qui va naître est PAYÉ : sans ce drapeau, on
            # débiterait le solde pour produire une traduction que son
            # acheteur ne pourrait ni voir en clair ni télécharger.
            doc_is_paid = True
    else:
        pages_set = cap_pages_for_plan(pages_set, ext, page_limit)

        # ── Plans payants : quota de pages du MOIS ────────────────────────────
        #
        # Distinct du plafond par document (`page_limit`), qui ne limite qu'une
        # traduction à la fois. Sans ce compteur, « 100 pages par mois » sur la
        # carte de tarifs voulait dire « autant de documents de 100 pages que
        # vous voulez » : le quota vendu n'existait tout simplement pas.
        monthly = get_plan_monthly_pages(plan)
        if monthly is not None:
            # Même verrou que pour le forfait Gratuit, et pour la même raison :
            # compter puis insérer est un lire-puis-écrire.
            await db.execute(
                select(User).where(User.id == current_user.id).with_for_update()
            )
            month_start = datetime.now(timezone.utc).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0)
            r = await db.execute(
                select(func.coalesce(func.sum(Document.page_count), 0)).where(
                    Document.user_id == current_user.id,
                    Document.created_at >= month_start,
                )
            )
            deja = int(r.scalar() or 0)
            demande = len(pages_set) if pages_set else count_pages(file_bytes, ext)
            if deja + demande > monthly:
                raise HTTPException(
                    status_code=402,
                    detail=(f"Vous avez déjà traduit {deja} page(s) ce mois-ci "
                            f"(limite : {monthly}). Ce document en demande {demande}. "
                            "Le compteur repart le 1er du mois prochain."),
                )

    # Ce qui sera RÉELLEMENT traduit — enregistré sur le Document, sinon le
    # quota du mois prochain n'aurait rien à compter (`page_count` restait NULL).
    pages_facturees = len(pages_set) if pages_set else count_pages(file_bytes, ext)

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
    if ext == "pdf":
        translation_path = os.path.join(lang_dir, f"pages{qsuffix}{psuffix}.json")
    else:
        translation_path = os.path.join(lang_dir, f"translated{qsuffix}{psuffix}.json")

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

    job_id = _new_job()
    # Rendu TRANSITOIRE, propre au job (nettoyé par le GC) : il sert le flux
    # progressif et le téléchargement immédiat, puis disparaît. La source de
    # vérité reste `translation_path`.
    output_path = os.path.join(lang_dir, f"render{qsuffix}{psuffix}_{job_id[:8]}.{ext}")
    with _jobs_lock:                    # propriétaire : /partial et /result s'en servent
        _jobs[job_id]["user_id"] = current_user.id
        # Pages RÉELLEMENT traduites : les seules à protéger dans l'aperçu
        # d'essai (les autres sont des copies de l'original). None = toutes.
        _jobs[job_id]["pages"] = set(pages_set) if pages_set else None
    if ext == "pdf":
        # PDF → moteur v2 PROGRESSIF : page traduite = page affichable.
        # `partial` grandit page à page ; `translation_path` (pages.json) = la
        # traduction persistante, qui sert aussi de cache de reprise.
        partial_path = os.path.join(lang_dir, f"partial{qsuffix}{psuffix}_{job_id[:8]}.pdf")
        thread = threading.Thread(
            target=_run_pdf_v2_job,
            args=(job_id, file_bytes, original_path, output_path,
                  output_filename, partial_path, translation_path, target_lang,
                  pages_set, debug_mode),
            daemon=True,
        )
    elif ext == "pptx":
        # PPTX → moteur progressif slide par slide (comme le PDF v2).
        # Si compte admin : 5 slides traduites en parallèle.
        partial_path = os.path.join(lang_dir, f"partial{qsuffix}{psuffix}_{job_id[:8]}.pdf")
        is_admin = (current_user.plan == "admin")
        thread = threading.Thread(
            target=_run_pptx_progressive_job,
            args=(job_id, file_bytes, original_path, output_path,
                  output_filename, partial_path, translation_path, target_lang,
                  pages_set, debug_mode, is_admin),
            daemon=True,
        )
    else:
        thread = threading.Thread(
            target=_run_translation_job,
            args=(job_id, file_bytes, filename, ext, target_lang, format_opts,
                  job_dir, lang_dir, original_path, extraction_path,
                  translation_path, output_path, output_filename,
                  model, max_tokens, pages_set, debug_mode),
            daemon=True,
        )
    # ── Document en base AVANT de démarrer le worker ─────────────────────
    # L'ordre est un garde-fou, pas un détail : la ligne Document est la seule
    # référence qui protège les octets partagés du magasin contre la purge d'un
    # autre compte (`_purge_if_orphan` compte les références en base). Insérer
    # après `thread.start()` ouvrait deux fenêtres : (1) A supprime son document
    # pendant que le job de B démarre → les fichiers communs sont purgés sous
    # ses pieds ; (2) un cache-hit terminait le job avant que `document_id` ne
    # soit lié → le Document restait « translating » pour toujours.
    await _save_document_for_user(current_user, db, job_id, filename,
                                  target_lang, original_path, len(file_bytes),
                                  paid=doc_is_paid, page_count=pages_facturees)

    thread.start()

    logger.info(f"Job {job_id} started for '{filename}' -> {target_lang}")
    return JSONResponse({"job_id": job_id})


@app.get("/api/translate/events/{job_id}")
async def translation_events(job_id: str, token: str = ""):
    """SSE endpoint : émet les events de progression jusqu'à done/error.

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

    with _jobs_lock:
        job = _jobs.get(job_id)
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
                    yield ": keepalive\n\n"
                    await asyncio.sleep(0.1)
                    continue

                data = json.dumps(msg, ensure_ascii=False)
                yield f"data: {data}\n\n"

                if msg.get("type") in ("done", "error"):
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
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job or job.get("user_id") != user.id:
        raise HTTPException(status_code=404, detail="Job introuvable.")
    return job


@app.get("/api/translate/partial/{job_id}")
async def translation_partial(job_id: str, x_api_key: str = Header(None),
                              current_user: "User" = Depends(require_auth)):
    """PDF PARTIEL d'un job v2 en cours : contient les pages 1..k déjà
    traduites (réécrit atomiquement après chaque page). Le client le recharge
    à chaque événement `page done` pour afficher la traduction au fil de l'eau."""
    verify_api_key(x_api_key)
    job = _job_of(job_id, current_user)
    path = job.get("partial_path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=202, detail="Aucune page prête pour l'instant.")
    with open(path, "rb") as f:
        data = f.read()

    # PLAN D'ESSAI : jamais le clair. On envoyait le PDF traduit tel quel et on
    # comptait sur le navigateur pour l'assombrir — mesuré : un compte `free`
    # récupérait le FICHIER (782 mots extractibles) en trois clics dans l'onglet
    # Réseau. Rastériser retire la couche texte : il ne reste que des pixels
    # filigranés, inexploitables sans OCR. Le projecteur au survol, lui, marche
    # toujours (il lui faut des pixels nets, il en a).
    # Liste d'AUTORISATION, pas de refus : un plan inconnu (valeur corrompue,
    # plan retiré du barème) est traité comme non payant. `== FREE_PLAN`
    # donnait l'inverse : tout ce qui n'était pas littéralement "free" passait.
    if not is_paid_plan(current_user.plan):
        data = rasterize_for_trial(data, job.get("pages"))

    return Response(content=data, media_type="application/pdf",
                    headers={"Cache-Control": "no-store"})


@app.get("/api/translate/result/{job_id}")
async def translation_result(job_id: str, x_api_key: str = Header(None),
                             current_user: "User" = Depends(require_auth)):
    """Retourne le fichier traduit une fois le job terminé.

    TÉLÉCHARGEMENT RÉSERVÉ AUX PLANS PAYANTS (décision produit). Le verrou
    n'existait que dans le frontend (bouton qui renvoyait vers la grille
    tarifaire) : un appel direct rendait le PDF complet à n'importe qui. Un
    verrou qui n'est pas appliqué par le serveur n'est pas un verrou.
    """
    verify_api_key(x_api_key)
    job = _job_of(job_id, current_user)
    if not is_paid_plan(current_user.plan):
        raise HTTPException(
            status_code=402,
            detail="Forfait Gratuit : téléchargement indisponible. "
                   "Passez à Starter pour télécharger vos traductions.",
        )
    if job["state"] == "error":
        raise HTTPException(status_code=500, detail="La traduction a échoué. Réessayez ou contactez le support si le problème persiste.")
    if job["state"] != "done":
        raise HTTPException(status_code=202, detail="Job en cours.")
    if not job["result_path"] or not os.path.exists(job["result_path"]):
        raise HTTPException(status_code=500, detail="Fichier résultat introuvable.")

    return FileResponse(
        job["result_path"],
        media_type="application/octet-stream",
        filename=job["result_filename"],
    )
