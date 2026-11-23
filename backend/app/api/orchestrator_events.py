"""Private signed Payment Orchestrator receipt. Feature-off means HTTP 404.

A 204 + event ACK is emitted only after durable SQL commit. No credit is
awarded here; local quote/order binding is a separate gate.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.orchestrator_payment_event import OrchestratorPaymentEvent
from app.services.orchestrator_events import (
    InvalidOrchestratorEvent, VerifiedOrchestratorEvent, verify_orchestrator_event
)

router = APIRouter(prefix="/api/payments/orchestrator", tags=["Paiements"])


def _receiver_config() -> tuple[str, str, str, str]:
    if os.getenv("PRECIS_ORCHESTRATOR_EVENTS_ENABLED") != "true":
        raise HTTPException(status_code=404, detail="Introuvable.")
    environment = os.getenv("PRECIS_ORCHESTRATOR_EVENTS_ENVIRONMENT", "")
    if environment not in ("sandbox", "live"):
        raise HTTPException(status_code=503, detail="Récepteur indisponible.")
    if (environment == "live" and
            os.getenv("PRECIS_ORCHESTRATOR_LIVE_APPROVED") != "true"):
        raise HTTPException(status_code=503, detail="Récepteur indisponible.")
    project_id = os.getenv("PRECIS_ORCHESTRATOR_EVENTS_PROJECT_ID", "")
    key_id = os.getenv("PRECIS_ORCHESTRATOR_EVENTS_KEY_ID", "")
    secret = os.getenv("PRECIS_ORCHESTRATOR_EVENTS_HMAC_SECRET", "")
    if not project_id or not key_id or len(secret) < 32:
        raise HTTPException(status_code=503, detail="Récepteur indisponible.")
    return environment, project_id, key_id, secret


async def _read_bounded(request: Request, max_bytes: int = 8192) -> bytes:
    if request.headers.get("content-length", "").isdigit():
        if int(request.headers["content-length"]) > max_bytes:
            raise HTTPException(status_code=413, detail="Corps trop volumineux.")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > max_bytes:
            raise HTTPException(status_code=413, detail="Corps trop volumineux.")
    return bytes(raw)


async def persist_orchestrator_event(
    db: AsyncSession, event: VerifiedOrchestratorEvent
) -> bool:
    """Return True for exact replay; different payload on same effect is 409.

    SQL unique constraints serialize concurrent duplicates across app replicas.
    Only evidence is stored: users, plans and page credits are untouched.
    """
    values = {
        "event_id": event.event_id, "effect_key": event.effect_key,
        "project_id": event.project_id, "environment": event.environment,
        "payment_id": event.payment_id, "merchant_id": event.merchant_id,
        "external_reference": event.external_reference,
        "provider_reference": event.provider_reference,
        "amount_minor": event.amount_minor, "currency": event.currency,
        "payload_digest": event.digest, "state": "pending_purchase_match"
    }
    stmt = insert(OrchestratorPaymentEvent).values(**values).on_conflict_do_nothing()
    result = await db.execute(stmt.returning(OrchestratorPaymentEvent.event_id))
    created = result.scalar_one_or_none()
    if created:
        await db.commit()
        return False

    prior_matches = (await db.execute(
        select(OrchestratorPaymentEvent).where(
            or_(
                OrchestratorPaymentEvent.event_id == event.event_id,
                (
                    (OrchestratorPaymentEvent.project_id == event.project_id) &
                    (OrchestratorPaymentEvent.environment == event.environment) &
                    (OrchestratorPaymentEvent.effect_key == event.effect_key)
                )
            )
        )
    )).scalars().all()
    # A forged/rotated valid HMAC could otherwise make two distinct unique
    # constraints match different rows. Never treat that as an internal 500.
    prior = prior_matches[0] if len(prior_matches) == 1 else None
    if prior is None or prior.event_id != event.event_id or (
        prior.project_id != event.project_id or
        prior.environment != event.environment or
        prior.effect_key != event.effect_key or
        prior.payload_digest != event.digest
    ):
        await db.rollback()
        raise HTTPException(status_code=409, detail="Événement contradictoire.")
    await db.commit()
    return True


@router.post("/events", include_in_schema=False, status_code=204)
async def orchestrator_event(request: Request, db: AsyncSession = Depends(get_db)):
    environment, project_id, key_id, secret = _receiver_config()
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(status_code=415, detail="Format non pris en charge.")
    for name in ("x-trigenys-event-id", "x-trigenys-key-id",
                 "x-trigenys-timestamp", "x-trigenys-signature"):
        if len(request.headers.getlist(name)) != 1:
            raise HTTPException(status_code=403, detail="Authentification invalide.")

    body = await _read_bounded(request)
    try:
        event = verify_orchestrator_event(
            request.headers, body,
            secret=secret, key_id=key_id, project_id=project_id,
            environment=environment,
        )
    except InvalidOrchestratorEvent:
        raise HTTPException(status_code=403, detail="Authentification invalide.")
    await persist_orchestrator_event(db, event)
    return Response(status_code=204, headers={"x-trigenys-event-ack": event.event_id})
