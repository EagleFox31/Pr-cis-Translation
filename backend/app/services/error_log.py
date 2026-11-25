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

from app.core.database import async_session
from app.models import ErrorLog, STATUS_NEW

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
    _session=None,
) -> None:
    """Écrit UNE occurrence, dans sa propre session. Ne lève jamais.

    `_session` : fabrique de sessions à utiliser à la place de la globale
    (écriture depuis une boucle jetable, cf. `log_error_threadsafe`)."""
    try:
        message = _truncate(message, _MAX_MESSAGE) or "(sans message)"
        stack = _truncate(stack, _MAX_STACK)
        fp = fingerprint(source, level, message, location)
        async with (_session or async_session)() as db:
            db.add(ErrorLog(
                source=source, level=level, message=message, stack=stack,
                context=context, user_id=user_id, user_email=user_email,
                fingerprint=fp, status=STATUS_NEW,
            ))
            await db.commit()
            if trigger_alert:
                from app.services.alertes_admin import apres_erreur
                await apres_erreur(db, source, level, message, location, fp)
    except Exception as exc:   # noqa: BLE001 — un journal ne casse rien
        # Dernier recours : la console. Surtout PAS le logger applicatif si le
        # handler DB est branché dessus (récursion).
        try:
            print(f"[error_log] écriture impossible : {exc}", flush=True)
        except Exception:
            pass


# Boucle principale d'uvicorn, retenue au démarrage (`install_db_log_handler`).
# Le moteur global et son pool de connexions y sont attachés : écrire depuis un
# thread passe donc PAR elle, jamais par une boucle jetable.
_boucle: asyncio.AbstractEventLoop | None = None


async def _log_error_hors_pool(source: str, message: str, **kw) -> None:
    """`log_error` sur un moteur DÉDIÉ sans pool, pour une boucle jetable.

    Réutiliser le pool global hors de sa boucle y remettait des connexions
    liées à une boucle morte : la requête suivante de l'application levait
    alors « attached to a different loop » (500 sur /api/auth/me)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.database import DATABASE_URL

    eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
    try:
        await log_error(source, message,
                        _session=async_sessionmaker(eng, expire_on_commit=False), **kw)
    finally:
        await eng.dispose()


def log_error_threadsafe(source: str, message: str, **kw) -> None:
    """Version appelable depuis un THREAD (worker de traduction) ou un contexte
    sync. Ne lève jamais.

    - dans la boucle principale : tâche planifiée ;
    - depuis un thread, boucle principale connue : confiée à cette boucle ;
    - sinon (script, tests, boucle fermée) : boucle jetable SANS le pool global.
    """
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            loop.create_task(log_error(source, message, **kw))
            return
        boucle = _boucle
        if boucle is not None and boucle.is_running() and not boucle.is_closed():
            asyncio.run_coroutine_threadsafe(log_error(source, message, **kw), boucle)
            return
        asyncio.run(_log_error_hors_pool(source, message, **kw))
    except Exception:
        pass


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
    """Branche le handler sur le logger racine, au niveau ERROR. Idempotent.

    Appelée depuis le démarrage de l'application (boucle en marche) : retient
    cette boucle pour les écritures venues des threads."""
    global _boucle
    try:
        _boucle = asyncio.get_running_loop()
    except RuntimeError:
        pass
    root = logging.getLogger()
    if any(isinstance(h, DBLogHandler) for h in root.handlers):
        return
    h = DBLogHandler(level=logging.ERROR)
    root.addHandler(h)
