import os
import json
import asyncio
import logging
import uuid
import queue
import threading
import shutil
import hashlib
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend_app")

FRONTEND_API_KEY = os.getenv("FRONTEND_API_KEY", "precis_frontend_secure_key_2026_xK9mP2vL")
MAX_FILE_SIZE = 10 * 1024 * 1024
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

app = FastAPI(title="Précis Translator API", version="1.0.0")

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

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("Slowapi rate limiter initialized successfully.")
except ImportError:
    limiter = None
    logger.warning("Slowapi library not found. Rate limiting is disabled.")

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
from pdf_translator_engine import PDFTranslatorEngine
try:
    from pptx_translator_engine import PPTXTranslatorEngine
except ImportError:
    PPTXTranslatorEngine = None
from translator_ai import TranslatorAI

docx_engine = DOCXTranslatorEngine()
pdf_engine = PDFTranslatorEngine()
try:
    if os.getenv("DEEPSEEK_API_KEY"):
        pdf_engine.configure_llm(os.getenv("DEEPSEEK_API_KEY"))
        logger.info("PDF engine LLM merge validation enabled.")
except Exception as e:
    logger.warning(f"PDF engine LLM not configured: {e}")
try:
    pptx_engine = PPTXTranslatorEngine() if PPTXTranslatorEngine else None
except:
    pptx_engine = None

try:
    ai_translator = TranslatorAI()
    ai_active = True
    logger.info("AI translator initialized successfully.")
except Exception as e:
    ai_active = False
    logger.warning(f"AI not initialized: {e}")

# Deux modes de traduction, choisis par requête via le paramètre `quality` :
#  • "fast"    → modèle non-raisonnant, ~secondes/page, version stable (défaut) ;
#  • "precise" → modèle à raisonnement, alignement id↔texte fiable sur les pages
#                complexes (numéros + formules), mais ~1-2 min/page.
# Noms surchargeables via .env si DeepSeek renomme ses modèles.
FAST_MODEL = os.getenv("DEEPSEEK_MODEL_FAST", "deepseek-chat")
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

def _new_job() -> str:
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "state": "pending",
            "q": queue.Queue(),
            "result_path": None,
            "result_filename": None,
            "error": None,
        }
    return job_id

def _job_emit(job_id: str, event_type: str, payload: dict):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job:
        job["q"].put({"type": event_type, **payload})

def _job_done(job_id: str, result_path: str, filename: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job:
        job["result_path"] = result_path
        job["result_filename"] = filename
        job["state"] = "done"
        job["q"].put({"type": "done", "filename": filename})

def _job_error(job_id: str, message: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job:
        job["error"] = message
        job["state"] = "error"
        job["q"].put({"type": "error", "message": message})

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
    model: str, max_tokens: int,
):
    """Exécute toute la pipeline dans un thread de fond et émet des events SSE."""
    try:
        _job_emit(job_id, "progress", {"step": "start", "message": "Démarrage du job...", "page": 0, "total": None})

        # 1. Cache final
        if os.path.exists(output_path):
            _job_emit(job_id, "progress", {"step": "cache", "message": "Résultat en cache, restitution immédiate.", "page": 0, "total": None})
            _job_done(job_id, output_path, output_filename)
            return

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
            elif ext == "pdf":
                extraction, _ = pdf_engine.extract_text(original_path, extraction_path, progress_callback=cb_extract)
            elif ext == "pptx" and pptx_engine:
                filters = {"shapes": True, "smartarts": True, "tables": True, "connectors": True}
                extraction, _ = pptx_engine.extract_text(original_path, extraction_path, filters=filters, progress_callback=cb_extract)
            else:
                raise ValueError(f"Type de fichier .{ext} non supporté.")
            if not extraction:
                if os.path.exists(extraction_path):
                    os.remove(extraction_path)
                raise ValueError("Échec de l'extraction du texte.")
        else:
            _job_emit(job_id, "progress", {"step": "extract", "message": "Extraction : cache utilisé.", "page": 0, "total": None})

        # 4. Traduction IA
        if not os.path.exists(translated_path):
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

        # 5. Injection / génération du PDF
        cb_inject = _make_progress_cb(job_id, "inject")
        _job_emit(job_id, "progress", {"step": "inject", "message": "Génération du document traduit...", "page": 0, "total": None})
        if ext == "docx":
            inj_ok, inj_msg = docx_engine.inject_translation(original_path, translated_path, output_path, format_options=format_opts)
        elif ext == "pdf":
            inj_ok, inj_msg = pdf_engine.inject_translation(original_path, translated_path, output_path, progress_callback=cb_inject, format_options=format_opts)
        elif ext == "pptx" and pptx_engine:
            inj_ok, inj_msg = pptx_engine.inject_translation(original_path, translated_path, output_path, format_options=format_opts)
        else:
            raise ValueError("Type de fichier non supporté pour la génération.")

        if not inj_ok:
            if os.path.exists(output_path):
                os.remove(output_path)
            raise ValueError(f"Injection échouée : {inj_msg}")

        if not os.path.exists(output_path):
            raise ValueError("Le fichier traduit est introuvable après génération.")

        _job_done(job_id, output_path, output_filename)

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        _job_error(job_id, str(e))


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

@app.post("/api/translate")
async def translate_endpoint(
    request: Request,
    file: UploadFile = File(...),
    target_lang: str = Form("en"),
    format_options: str = Form("{}"),
    quality: str = Form("fast"),
    x_api_key: str = Header(None),
):
    """Démarre un job de traduction et retourne immédiatement un job_id.
    Le client peut ensuite écouter /api/translate/events/{job_id} (SSE)
    pour suivre la progression, puis télécharger via /api/translate/result/{job_id}."""
    verify_api_key(x_api_key)

    filename = file.filename or ""
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Type non supporté : .{ext}")

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lecture du fichier impossible : {e}")

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"Fichier trop volumineux ({len(file_bytes)/(1024*1024):.1f} Mo, max 10 Mo).")

    try:
        format_opts = json.loads(format_options) if format_options else {}
    except json.JSONDecodeError:
        format_opts = {}

    # Mode de traduction (rapide vs précis) → modèle + budget de tokens.
    quality = quality if quality in ("fast", "precise") else "fast"
    model, max_tokens = _resolve_quality(quality)
    # Suffixe de cache : les deux modes produisent des résultats différents, ils
    # ne doivent JAMAIS partager le même translated.json ni le même PDF de sortie.
    qsuffix = "" if quality == "fast" else "_precise"

    file_hash = get_file_hash(file_bytes)
    safe_name = sanitize_filename(filename)
    job_dir = os.path.join(TRANSLATIONS_DIR, f"{safe_name}_{file_hash}")
    lang_dir = os.path.join(job_dir, target_lang)
    os.makedirs(lang_dir, exist_ok=True)

    original_path = os.path.join(job_dir, f"original.{ext}")
    extraction_path = os.path.join(job_dir, "extraction.json")
    translated_path = os.path.join(lang_dir, f"translated{qsuffix}.json")

    output_filename = f"{safe_name}_TRADUIT{qsuffix}.{ext}"
    if format_opts.get("mode") and format_opts["mode"] != "preserve":
        output_filename = f"{safe_name}_TRADUIT{qsuffix}_{format_opts['mode']}.{ext}"
    layout_opts = format_opts.get("layout")
    if layout_opts:
        import hashlib as _hl
        layout_sig = _hl.sha1(json.dumps(layout_opts, sort_keys=True).encode()).hexdigest()[:10]
        base, dot, fext = output_filename.rpartition(".")
        output_filename = f"{base}_L{layout_sig}{dot}{fext}"
    output_path = os.path.join(lang_dir, output_filename)

    job_id = _new_job()
    thread = threading.Thread(
        target=_run_translation_job,
        args=(job_id, file_bytes, filename, ext, target_lang, format_opts,
              job_dir, lang_dir, original_path, extraction_path,
              translated_path, output_path, output_filename,
              model, max_tokens),
        daemon=True,
    )
    thread.start()

    logger.info(f"Job {job_id} started for '{filename}' -> {target_lang}")
    return JSONResponse({"job_id": job_id})


@app.get("/api/translate/events/{job_id}")
async def translation_events(job_id: str):
    """SSE endpoint : émet les events de progression jusqu'à done/error.
    Pas de vérification API key : EventSource (navigateur) ne supporte pas
    les headers custom. Le job_id UUID sert de token d'accès."""

    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
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


@app.get("/api/translate/result/{job_id}")
async def translation_result(job_id: str, x_api_key: str = Header(None)):
    """Retourne le fichier traduit une fois le job terminé."""
    verify_api_key(x_api_key)

    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job introuvable.")
    if job["state"] == "error":
        raise HTTPException(status_code=500, detail=job.get("error", "Erreur inconnue."))
    if job["state"] != "done":
        raise HTTPException(status_code=202, detail="Job en cours.")
    if not job["result_path"] or not os.path.exists(job["result_path"]):
        raise HTTPException(status_code=500, detail="Fichier résultat introuvable.")

    return FileResponse(
        job["result_path"],
        media_type="application/octet-stream",
        filename=job["result_filename"],
    )
