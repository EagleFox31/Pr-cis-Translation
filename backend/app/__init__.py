"""Fabrique de l'application FastAPI.

POURQUOI UNE FABRIQUE ET NON UN `app = FastAPI()` DE MODULE
-----------------------------------------------------------
L'instance vivait au niveau du module, entourée de tout ce qui la configurait :
routes décorées, middleware, moteurs chargés, thread de pré-chauffage lancé.
Importer le module — pour un test, pour un script d'administration, pour lire
une constante — exécutait donc TOUT cela.

Avec `create_app()`, l'import ne fait rien ; c'est l'appel qui construit. Un
test peut monter une instance propre, un script peut importer un service sans
réveiller LibreOffice, et l'ordre de construction est lisible en un écran.

L'ORDRE DES DÉPENDANCES
-----------------------
    app.api  ->  app.services  ->  engines  ->  (rien du projet)
    app.api  ->  app.core      ->  (rien du projet)

Aucune flèche ne remonte. C'est ce qui permet de sortir un moteur du projet, ou
d'appeler un service depuis un script, sans rien entraîner derrière.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS, STARTUP_NOTES, logger

__all__ = ["create_app"]


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Démarrage et arrêt.

    Les messages d'init sont affichés ICI et pas à l'import : sous
    `uvicorn --reload`, le module est chargé deux fois (process parent + worker)
    et chaque ligne apparaissait en double. Seul le worker traverse le lifespan.
    """
    from app.services import office
    from app.services.startup import (balayer_partiels_orphelins,
                                      reconcilier_jobs_orphelins)

    for _level, message in STARTUP_NOTES:
        print(message, flush=True)
    await reconcilier_jobs_orphelins()
    balayer_partiels_orphelins()
    office.prewarm()
    yield


def create_app() -> FastAPI:
    """Construit et câble l'application."""
    application = FastAPI(
        title="Précis Translator API",
        version="1.0.0",
        description=(
            "Traduction de documents à mise en forme préservée — PDF, PPTX, "
            "DOCX. Le texte est relevé avec sa géométrie et ses styles, "
            "traduit, puis réinjecté dans le document d'origine."
        ),
        lifespan=_lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def log_requests(request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        logger.info(f"Incoming request from IP: {ip} | Method: {request.method} "
                    f"| Path: {request.url.path}")
        response = await call_next(request)
        logger.info(f"Response status for IP {ip}: {response.status_code}")
        return response

    # Limitation de débit : `limiter` est None si slowapi manque, et
    # `rate_limit_decorator` devient alors neutre. Rien d'autre ne change.
    from app.rate_limit import limiter
    if limiter is not None:
        from slowapi import _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        application.state.limiter = limiter
        application.add_exception_handler(RateLimitExceeded,
                                          _rate_limit_exceeded_handler)

    # Les routeurs sont importés ICI, pas en tête de module : ils tirent les
    # services, qui tirent les moteurs. Au niveau du module, ce chargement
    # partirait au simple `import app`.
    from app.api.auth import router as auth_router
    from app.api.documents import router as documents_router
    from app.api.payments import router as payments_router
    from app.api.system import router as system_router
    from app.api.translate import router as translate_router

    for router in (auth_router, documents_router, payments_router,
                   system_router, translate_router):
        application.include_router(router)

    return application
