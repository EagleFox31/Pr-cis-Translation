"""Écriture du journal d'erreurs — depuis n'importe où, sans jamais casser l'app.

Une erreur peut survenir dans une requête (contexte async), dans un thread de
traduction (aucune boucle d'événements), ou passer par le logger Python. Ce
module offre un point d'entrée pour chacun, tous convergeant vers `log_error` —
et TOUS avalent leurs propres exceptions : un journal qui plante en journalisant
est pire que pas de journal du tout.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import threading
import time

from sqlalchemy import func, select

from app.config import (ADMIN_ALERT_EMAIL, ERROR_LOG_ALERT_COOLDOWN,
                        ERROR_LOG_ALERT_THRESHOLD)
from app.core.database import async_session
from app.models import ErrorLog, STATUS_NEW, User

# Bornes : un message ou une pile démesurés ne doivent ni saturer la base ni
# ralentir l'affichage. On tronque à l'écriture — la queue de trace suffit
# largement à identifier un défaut.
_MAX_MESSAGE = 2000
_MAX_STACK = 16000

# Garde-fou anti-récursion pour le handler de logging : pendant qu'on persiste un
# log, toute erreur émise par SQLAlchemy/asyncpg NE doit pas déclencher un nouveau
# log persistant, sinon boucle. Ce drapeau par thread coupe la ré-entrée.
_persisting = threading.local()


def _truncate(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    text = str(text)
    return text if len(text) <= limit else text[:limit] + "…[tronqué]"


def fingerprint(source: str, level: str, message: str, location: str = "") -> str:
    """Empreinte STABLE d'un groupe d'erreurs identiques.

    Le message brut varie parfois (identifiants, chemins) : on retient sa tête,
    la source, le niveau et une localisation (route, composant). Deux occurrences
    du même défaut tombent sur la même empreinte — c'est la clé du regroupement.
    """
    head = (message or "").strip()[:200]
    raw = f"{source}|{level}|{location}|{head}"
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:32]


async def log_error(
    source: str,
    message: str,
    *,
    level: str = "error",
    stack: str | None = None,
    context: dict | None = None,
    location: str = "",
    user_id: str | None = None,
    user_email: str | None = None,
    trigger_alert: bool = True,
) -> None:
    """Écrit UNE occurrence, dans sa propre session. Ne lève jamais."""
    try:
        message = _truncate(message, _MAX_MESSAGE) or "(sans message)"
        stack = _truncate(stack, _MAX_STACK)
        fp = fingerprint(source, level, message, location)
        async with async_session() as db:
            db.add(ErrorLog(
                source=source, level=level, message=message, stack=stack,
                context=context, user_id=user_id, user_email=user_email,
                fingerprint=fp, status=STATUS_NEW,
            ))
            await db.commit()
            if trigger_alert:
                await maybe_alert_admins(db)
    except Exception as exc:   # noqa: BLE001 — un journal ne casse rien
        # Dernier recours : la console. Surtout PAS le logger applicatif si le
        # handler DB est branché dessus (récursion).
        try:
            print(f"[error_log] écriture impossible : {exc}", flush=True)
        except Exception:
            pass


def log_error_threadsafe(source: str, message: str, **kw) -> None:
    """Version appelable depuis un THREAD (worker de traduction) ou un contexte
    sync. Route vers `log_error` selon qu'une boucle tourne ou non."""
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            loop.create_task(log_error(source, message, **kw))
        else:
            asyncio.run(log_error(source, message, **kw))
    except Exception:
        pass


# ── Alerte admin au seuil ─────────────────────────────────────────────────────

_last_alert_at = 0.0
_alert_lock = threading.Lock()


async def maybe_alert_admins(db) -> bool:
    """Si les logs NON traités franchissent le seuil, prévient l'admin — au plus
    une fois par cooldown. Retourne True si un e-mail a été (tenté d')envoyé."""
    global _last_alert_at
    try:
        count = await db.scalar(
            select(func.count()).select_from(ErrorLog).where(ErrorLog.status == STATUS_NEW)
        )
        if not count or count < ERROR_LOG_ALERT_THRESHOLD:
            return False

        now = time.time()
        with _alert_lock:
            if now - _last_alert_at < ERROR_LOG_ALERT_COOLDOWN:
                return False
            _last_alert_at = now

        rows = await db.execute(select(User.email).where(User.plan == "admin"))
        emails = [e for (e,) in rows.all() if e]
        if not emails and ADMIN_ALERT_EMAIL:
            emails = [ADMIN_ALERT_EMAIL]
        if not emails:
            return False

        from app.core.email import send_plain
        await send_plain(
            emails,
            f"[Précis] {count} erreurs à traiter",
            f"{count} erreurs non traitées se sont accumulées dans le journal.\n"
            f"Ouvre /admin/logs pour les consigner puis les vider.",
        )
        return True
    except Exception:
        return False


# ── Catch-all : tout logger.error/exception atterrit aussi dans le journal ─────

class DBLogHandler(logging.Handler):
    """Persiste chaque enregistrement ERROR/CRITICAL du logging Python.

    C'est le filet « absolument toutes » : un `logger.error(...)` posé n'importe
    où dans le backend finit dans le journal, sans que l'auteur ait à le savoir.
    Re-entrée coupée (le drapeau par thread), pour ne pas boucler si l'écriture
    elle-même émet un log.
    """

    # Loggers d'infrastructure : bruyants et hors de notre code. Les persister
    # noierait le journal (et un log d'erreur SQL pendant l'écriture pourrait
    # boucler). On ne garde que les erreurs applicatives.
    _IGNORE_PREFIXES = ("sqlalchemy", "asyncpg", "aiosmtplib", "uvicorn.access",
                        "watchfiles", "multipart")

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(_persisting, "on", False):
            return
        if record.name.startswith(self._IGNORE_PREFIXES):
            return
        try:
            _persisting.on = True
            msg = record.getMessage()
            stack = None
            if record.exc_info:
                stack = logging.Formatter().formatException(record.exc_info)
            level = "critical" if record.levelno >= logging.CRITICAL else "error"
            log_error_threadsafe(
                "backend", msg, level=level, stack=stack,
                location=f"{record.module}.{record.funcName}",
                context={"logger": record.name},
            )
        except Exception:
            pass
        finally:
            _persisting.on = False


def install_db_log_handler() -> None:
    """Branche le handler sur le logger racine, au niveau ERROR. Idempotent."""
    root = logging.getLogger()
    if any(isinstance(h, DBLogHandler) for h in root.handlers):
        return
    h = DBLogHandler(level=logging.ERROR)
    root.addHandler(h)
