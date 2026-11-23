"""Anti-robots à la création de compte (Cloudflare Turnstile).

Le widget du navigateur rend un jeton à usage unique (valable 300 s) ; seul
l'appel serveur `siteverify` dit s'il est authentique. Sans clé secrète
configurée, le contrôle est désactivé (développement, tests).

Une panne réseau vers Cloudflare laisse passer, avec un journal : bloquer
toutes les inscriptions pendant une panne coûterait plus que quelques robots,
qui restent freinés par les e-mails jetables refusés et le score de risque des
pages offertes (cf. docs/etude-anti-abus.md).
"""
from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException, Request

from app import config

logger = logging.getLogger(__name__)

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
MESSAGE = "La vérification anti-robot a échoué. Rechargez la page et réessayez."
MAX_TOKEN_LEN = 2048


async def _siteverify(data: dict) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(SITEVERIFY_URL, data=data)
        response.raise_for_status()
        return response.json()


async def require(request: Request, token: str | None):
    """Lève 400 si le jeton est absent ou refusé par Cloudflare."""
    secret = config.TURNSTILE_SECRET_KEY
    if not secret:
        return
    if not token or len(token) > MAX_TOKEN_LEN:
        raise HTTPException(400, MESSAGE)
    data = {"secret": secret, "response": token}
    if request.client and request.client.host:
        data["remoteip"] = request.client.host
    try:
        result = await _siteverify(data)
    except (httpx.HTTPError, ValueError):
        logger.warning("Turnstile : siteverify injoignable, inscription laissée passer")
        return
    if not result.get("success"):
        logger.info("Turnstile : jeton refusé (%s)", result.get("error-codes"))
        raise HTTPException(400, MESSAGE)
