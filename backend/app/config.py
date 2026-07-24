"""Configuration : tout ce que l'environnement décide, lu en UN seul endroit.

Avant, `os.getenv` était appelé depuis huit modules. Retrouver ce qu'une
variable pilotait supposait de fouiller le dépôt, et une valeur par défaut
pouvait différer d'un appel à l'autre sans que rien ne le signale.

Les chemins sont dérivés de l'emplacement de ce fichier, jamais du répertoire
courant : l'application doit se comporter pareil qu'on la lance depuis la
racine du dépôt, depuis `backend/`, ou via un service système.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# `backend/` — deux crans au-dessus de `backend/app/config.py`.
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

# Charger .env depuis le dossier backend/, quel que soit le cwd
load_dotenv(BACKEND_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
logger = logging.getLogger("backend_app")

# Sous `uvicorn --reload`, le module applicatif est importé DEUX fois : dans le
# process parent (qui appelle load_app() pour échouer vite) et dans le worker.
# Les messages d'init sont donc empilés ici puis émis dans le lifespan, que seul
# le worker traverse — sinon chaque ligne apparaît en double au démarrage.
STARTUP_NOTES: list[tuple[int, str]] = []


def note(level: int, message: str) -> None:
    """Empile un message d'initialisation, affiché au démarrage du worker."""
    STARTUP_NOTES.append((level, message))


# ── Accès ────────────────────────────────────────────────────────────────────
FRONTEND_API_KEY = os.getenv(
    "FRONTEND_API_KEY", "precis_frontend_secure_key_2026_xK9mP2vL")

_DEV_ORIGINS = [
    "http://localhost:5173", "http://localhost:3000", "http://localhost:3001",
    "http://127.0.0.1:5173", "http://127.0.0.1:3000", "http://127.0.0.1:3001",
]
_origins_str = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:8000,http://127.0.0.1:5173,"
    "http://127.0.0.1:8000,http://localhost:3000,http://localhost:3001,"
    "http://127.0.0.1:3001")
ALLOWED_ORIGINS = list(set(
    [o.strip() for o in _origins_str.split(",") if o.strip()] + _DEV_ORIGINS))

# ── Envois ───────────────────────────────────────────────────────────────────
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 Mo
ALLOWED_EXTENSIONS = {"txt", "pdf", "docx", "pptx", "xlsx"}

# ── Stockage ─────────────────────────────────────────────────────────────────
TRANSLATIONS_DIR = str(BACKEND_DIR / "translations")
os.makedirs(TRANSLATIONS_DIR, exist_ok=True)

# L'aperçu côte-à-côte s'appuie sur pdf.js : pour obtenir un rendu EXACT des
# formats non-PDF (DOCX, PPTX, TXT), on les convertit en PDF via LibreOffice
# headless. La conversion ne sert QUE l'aperçu — le téléchargement garde le
# format d'origine. Résultats mis en cache disque (clé = hash du contenu).
PREVIEW_CACHE_DIR = os.path.join(TRANSLATIONS_DIR, "_previews")

# ── Rétention des jobs ───────────────────────────────────────────────────────
# Un job terminé reste consultable (partiel/résultat) pendant cette durée, puis
# est oublié et son PDF partiel effacé. Le commentaire d'origine promettait ce
# ménage (« nettoyés après 30 minutes ») mais RIEN ne l'implémentait : les jobs
# s'accumulaient en mémoire et les partial_*.pdf sur le disque, sans borne.
JOB_RETENTION_SECONDS = 30 * 60
# Un job encore « en vie » au-delà de cette durée a perdu son worker (plantage
# sans job_error) : on l'oublie aussi.
JOB_MAX_AGE_SECONDS = 24 * 3600
# Intervalle minimal entre deux écritures d'avancement en base.
PROGRESS_EVERY_S = 3.0

# ── Ordonnanceur de traduction ───────────────────────────────────────────────
# Nombre de traductions menées EN PARALLÈLE. Au-delà, les demandes attendent
# dans une file de PRIORITÉ (le plan décide de l'ordre : admin > pro > starter >
# gratuit). C'est ce qui donne corps à la vitesse vendue sur la carte de tarifs.
#
# Le coût dominant d'une traduction est le CPU de rendu : trop de workers sur
# une seule machine se marchent dessus et RALENTISSENT tout le monde. 2 est un
# défaut prudent pour un mono-serveur ; à monter avec le nombre de cœurs.
TRANSLATION_WORKERS = max(1, int(os.getenv("TRANSLATION_WORKERS", "2")))

# ── Modèles de traduction ────────────────────────────────────────────────────
# Deux modes, choisis par requête via le paramètre `quality` :
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


# ── Marque publique ──────────────────────────────────────────────────────────
# Nom et adresse du service, tels qu'ils apparaissent DANS l'aperçu d'essai
# (filigrane = mini-publicité). Configurables : au changement de domaine, on ne
# recompile pas le moteur d'aperçu. Le filigrane est cuit dans les pixels, donc
# ces valeurs se figent au moment du rendu — un aperçu ancien garde l'ancien
# libellé, ce qui est sans conséquence.
BRAND_NAME = os.getenv("BRAND_NAME", "PRÉCIS")
BRAND_TAGLINE = os.getenv("BRAND_TAGLINE", "Professional Translation")
PUBLIC_SITE = os.getenv("PUBLIC_SITE", "precis-translator.com")


# ── Journal des erreurs ──────────────────────────────────────────────────────
# Au-delà de ce nombre de logs NON traités, l'admin reçoit une alerte e-mail —
# une seule à la fois (throttle), pour signaler qu'il y a du grain à moudre sans
# noyer sa boîte. Puis il traite (exporte) et supprime : la table ne gonfle que
# tant qu'on ne s'en occupe pas.
ERROR_LOG_ALERT_THRESHOLD = int(os.getenv("ERROR_LOG_ALERT_THRESHOLD", "50"))
ERROR_LOG_ALERT_COOLDOWN = int(os.getenv("ERROR_LOG_ALERT_COOLDOWN", "3600"))  # s
# Destinataire de repli si AUCUN compte n'a le plan `admin` en base (bootstrap).
ADMIN_ALERT_EMAIL = os.getenv("ADMIN_ALERT_EMAIL") or None


def resolve_quality(quality: str) -> tuple[str, int]:
    """(model, max_tokens) selon le mode demandé. Le mode précis a besoin d'un
    gros budget de tokens car le raisonnement en consomme avant la réponse."""
    if quality == "precise":
        return PRECISE_MODEL, 65536
    return FAST_MODEL, 8192
