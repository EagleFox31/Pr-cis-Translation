import os
import json
import logging
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from dotenv import load_dotenv
import tempfile
import shutil
import hashlib

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend_app")

FRONTEND_API_KEY = os.getenv("FRONTEND_API_KEY", "precis_frontend_secure_key_2026_xK9mP2vL")
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {"txt", "pdf", "docx", "pptx"}

TRANSLATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translations")
os.makedirs(TRANSLATIONS_DIR, exist_ok=True)

def get_file_hash(file_bytes: bytes) -> str:
    """Generate a short hash from file content for deduplication."""
    return hashlib.sha256(file_bytes).hexdigest()[:12]

def sanitize_filename(name: str) -> str:
    """Clean filename for use as directory name."""
    stem = os.path.splitext(name)[0]
    cleaned = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in stem)
    cleaned = "_".join(cleaned.split())
    return cleaned[:50] or "document"

app = FastAPI(title="Précis Translator API", version="1.0.0")

origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8000,http://127.0.0.1:5173,http://127.0.0.1:8000,http://localhost:3000,http://localhost:3001,http://127.0.0.1:3001")
origins = [o.strip() for o in origins_str.split(",") if o.strip()]

dev_origins = [
    "http://localhost:5173", "http://localhost:3000", "http://localhost:3001",
    "http://127.0.0.1:5173", "http://127.0.0.1:3000", "http://127.0.0.1:3001"
]
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

def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key:
        logger.warning("Request missing X-API-Key header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header"
        )
    if x_api_key != FRONTEND_API_KEY:
        logger.warning("Request provided an invalid X-API-Key.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-API-Key"
        )

from docx_translator_engine import DOCXTranslatorEngine
from pdf_translator_engine import PDFTranslatorEngine
try:
    from pptx_translator_engine import PPTXTranslatorEngine
except ImportError:
    PPTXTranslatorEngine = None
from translator_ai import TranslatorAI

docx_engine = DOCXTranslatorEngine()
pdf_engine = PDFTranslatorEngine()
# Validation IA des fusions de blocs ambiguës (même paragraphe ou non) à
# l'extraction PDF : sans cette configuration, seule la géométrie décide.
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

@app.get("/health")
@rate_limit_decorator("10/minute")
async def health_check(request: Request):
    return {"status": "healthy", "service": "Précis Translator API"}

@app.options("/api/translate")
async def translate_options():
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, X-API-Key",
        }
    )

@app.post("/api/translate")
async def translate_endpoint(
    request: Request,
    file: UploadFile = File(...),
    target_lang: str = Form("en"),
    format_options: str = Form("{}"),
    x_api_key: str = Header(None)
):
    verify_api_key(x_api_key)

    filename = file.filename or ""
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        logger.warning(f"Rejected file with unsupported extension: .{ext}")
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{ext}. Only .txt, .pdf, .docx, and .pptx files are allowed."
        )

    try:
        file_bytes = await file.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(status_code=400, detail="Failed to read uploaded file.")

    if len(file_bytes) > MAX_FILE_SIZE:
        logger.warning(f"File too large: {len(file_bytes)} bytes (Max 10MB)")
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum size limit of 10MB. Uploaded size: {len(file_bytes) / (1024 * 1024):.2f}MB"
        )

    # Parse format options
    try:
        format_opts = json.loads(format_options) if format_options else {}
    except json.JSONDecodeError:
        format_opts = {}

    logger.info(f"Processing file '{filename}' ({len(file_bytes)} bytes)... Format options: {format_opts}")

    # --- Persistent storage setup ---
    file_hash = get_file_hash(file_bytes)
    safe_name = sanitize_filename(filename)
    job_dir = os.path.join(TRANSLATIONS_DIR, f"{safe_name}_{file_hash}")
    lang_dir = os.path.join(job_dir, target_lang)
    os.makedirs(lang_dir, exist_ok=True)

    original_path = os.path.join(job_dir, f"original.{ext}")
    extraction_path = os.path.join(job_dir, "extraction.json")
    translated_path = os.path.join(lang_dir, "translated.json")

    # Create format-specific output path based on format options
    output_filename = f"{safe_name}_TRADUIT.{ext}"
    if format_opts.get('mode') and format_opts['mode'] != 'preserve':
        output_filename = f"{safe_name}_TRADUIT_{format_opts['mode']}.{ext}"
    # Per-page layout strategy (auto/reflow/shrink + scope) changes the rendered
    # output but not the extraction/translation. Fold it into the cache key so
    # each distinct strategy gets its own cached file (re-generation is cheap:
    # extraction + translation are reused).
    layout_opts = format_opts.get('layout')
    if layout_opts:
        layout_sig = hashlib.sha1(
            json.dumps(layout_opts, sort_keys=True).encode("utf-8")
        ).hexdigest()[:10]
        base, dot, fext = output_filename.rpartition(".")
        output_filename = f"{base}_L{layout_sig}{dot}{fext}"
    output_path = os.path.join(lang_dir, output_filename)

    try:
        # 1. Return cached result if the final output already exists
        if os.path.exists(output_path):
            logger.info(f"Cache hit: returning existing translation for '{filename}' -> {target_lang}")
            return FileResponse(output_path, media_type="application/octet-stream", filename=output_filename)

        # 2. Save original document (needed for the injection step)
        if not os.path.exists(original_path):
            with open(original_path, "wb") as f:
                f.write(file_bytes)

        # 3. Extract text if not already done
        if not os.path.exists(extraction_path):
            extraction = None
            if ext == "docx":
                filters = {"paragraphs": True, "tables": True, "headers_footers": True, "text_boxes": True, "smartarts": True}
                extraction, _ = docx_engine.extract_text(original_path, extraction_path, filters=filters)
            elif ext == "pdf":
                extraction, _ = pdf_engine.extract_text(original_path, extraction_path)
            elif ext == "pptx" and pptx_engine:
                filters = {"shapes": True, "smartarts": True, "tables": True, "connectors": True}
                extraction, _ = pptx_engine.extract_text(original_path, extraction_path, filters=filters)
            else:
                raise HTTPException(status_code=400, detail=f"File type .{ext} not fully supported yet.")

            if not extraction:
                if os.path.exists(extraction_path):
                    os.remove(extraction_path)
                raise HTTPException(status_code=500, detail="Failed to extract text from document.")
        else:
            logger.info(f"Extraction cache hit: reusing '{extraction_path}'")

        # 4. Translate via AI if not already done for this language
        if not os.path.exists(translated_path):
            if not ai_active:
                raise HTTPException(status_code=500, detail="AI translator is not available.")
            success, result = ai_translator.translate_json(extraction_path, target_lang=target_lang,
                                                           progress_callback=logger.info)
            if not success:
                logger.error(f"Translation failed for '{filename}': {result}")
                raise HTTPException(status_code=500, detail=f"Translation failed: {result}")
            # translate_json writes to extraction_translated.json next to source; move to lang dir
            logger.info(f"translate_json returned result path: '{result}' (exists={os.path.exists(result)})")
            if os.path.exists(result) and os.path.abspath(result) != os.path.abspath(translated_path):
                shutil.move(result, translated_path)
                logger.info(f"Moved translated JSON to '{translated_path}'")
        else:
            logger.info(f"Translation cache hit: reusing '{translated_path}'")

        # 5. Generate the final translated document with format options
        if ext == "docx":
            inj_success, inj_msg = docx_engine.inject_translation(original_path, translated_path, output_path, format_options=format_opts)
        elif ext == "pdf":
            inj_success, inj_msg = pdf_engine.inject_translation(original_path, translated_path, output_path,
                progress_callback=logger.info, format_options=format_opts)
        elif ext == "pptx" and pptx_engine:
            inj_success, inj_msg = pptx_engine.inject_translation(original_path, translated_path, output_path, format_options=format_opts)
        else:
            raise HTTPException(status_code=400, detail="File type not supported for translation generation.")

        if not inj_success:
            logger.error(f"Injection failed for '{filename}': {inj_msg}")
            if os.path.exists(output_path):
                os.remove(output_path)
            raise HTTPException(status_code=500, detail=f"Failed to generate translated file: {inj_msg}")

        if not os.path.exists(output_path):
            logger.error(f"Output file missing after injection: '{output_path}'")
            raise HTTPException(status_code=500, detail="Translated file was not created.")

        logger.info(f"Translation complete: '{output_path}'")
        return FileResponse(output_path, media_type="application/octet-stream", filename=output_filename)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during translation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Translation error: {str(e)}")