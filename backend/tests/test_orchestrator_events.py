"""Signed Payment Orchestrator receipt: exact HMAC, replay and durable SQL inbox.

Run: python tests/test_orchestrator_events.py
No Fapshi calls, real payments or page credits.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
import uuid

import racine  # noqa: F401
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app import create_app
from app.core.database import async_session
from app.models.orchestrator_payment_event import OrchestratorPaymentEvent

SECRET = "orchestrator-ci-hmac-" + uuid.uuid4().hex
PROJECT = "precis-ci-project"
EVENT_ID = str(uuid.uuid4())
EFFECT = "confirmed-" + uuid.uuid4().hex
ORIGIN = "/api/payments/orchestrator/events"

ENV_KEYS = (
    "PRECIS_ORCHESTRATOR_EVENTS_ENABLED",
    "PRECIS_ORCHESTRATOR_EVENTS_ENVIRONMENT",
    "PRECIS_ORCHESTRATOR_EVENTS_PROJECT_ID",
    "PRECIS_ORCHESTRATOR_EVENTS_KEY_ID",
    "PRECIS_ORCHESTRATOR_EVENTS_HMAC_SECRET",
    "PRECIS_ORCHESTRATOR_LIVE_APPROVED",
)


def body(event_id=EVENT_ID, effect=EFFECT, amount=150, project=PROJECT):
    data = {
        "eventType": "payment.confirmed", "projectId": project,
        "merchantId": "ci-merchant", "paymentId": "ci-payment",
        "externalReference": "ci-order", "provider": "fapshi",
        "providerReference": "ci-fapshi-ref", "currency": "XAF",
        "amountMinor": amount,
    }
    return json.dumps({
        "version": 1, "eventId": event_id, "effectKey": effect,
        "environment": "sandbox", "type": "payment.confirmed",
        "projectId": project, "paymentId": "ci-payment", "data": data,
    }, separators=(",", ":")).encode()


def signed(payload, event_id=EVENT_ID, stamp=None, secret=SECRET):
    stamp = str(int(time.time()) if stamp is None else stamp)
    text = b"v1\n" + stamp.encode() + b"\n" + event_id.encode() + b"\n" + payload
    signature = hmac.new(secret.encode(), text, hashlib.sha256).hexdigest()
    return {
        "content-type": "application/json",
        "x-trigenys-event-id": event_id,
        "x-trigenys-key-id": "precis-ci-v1",
        "x-trigenys-timestamp": stamp,
        "x-trigenys-signature": "v1=" + signature,
    }


async def persisted(event_id):
    async with async_session() as db:
        return (await db.execute(
            select(OrchestratorPaymentEvent).where(
                OrchestratorPaymentEvent.event_id == event_id
            )
        )).scalar_one_or_none()


async def cleanup():
    async with async_session() as db:
        await db.execute(delete(OrchestratorPaymentEvent).where(
            OrchestratorPaymentEvent.project_id == PROJECT
        ))
        await db.commit()


def run():
    snapshot = {key: os.environ.get(key) for key in ENV_KEYS}
    try:
        for key in ENV_KEYS:
            os.environ.pop(key, None)
        client = TestClient(create_app())
        p = body()

        assert client.post(ORIGIN, content=p, headers=signed(p)).status_code == 404
        os.environ.update({
            "PRECIS_ORCHESTRATOR_EVENTS_ENABLED": "true",
            "PRECIS_ORCHESTRATOR_EVENTS_ENVIRONMENT": "sandbox",
            "PRECIS_ORCHESTRATOR_EVENTS_PROJECT_ID": PROJECT,
            "PRECIS_ORCHESTRATOR_EVENTS_KEY_ID": "precis-ci-v1",
            "PRECIS_ORCHESTRATOR_EVENTS_HMAC_SECRET": SECRET,
        })
        assert client.post(ORIGIN, content=p, headers={
            **signed(p), "x-trigenys-signature": "v1=" + "0" * 64
        }).status_code == 403
        assert client.post(ORIGIN, content=p,
                           headers=signed(p, stamp=int(time.time()) - 900)).status_code == 403
        assert client.post(ORIGIN, content=p, headers=signed(p, secret="wrong-" + SECRET)).status_code == 403
        assert client.post(ORIGIN, content=p,
                           headers=signed(p, event_id="another-event")).status_code == 403
        different_project = body(project="foreign-project")
        assert client.post(ORIGIN, content=different_project,
                           headers=signed(different_project)).status_code == 403

        accepted = client.post(ORIGIN, content=p, headers=signed(p))
        assert accepted.status_code == 204, accepted.text
        assert accepted.headers.get("x-trigenys-event-ack") == EVENT_ID
        saved = asyncio.run(persisted(EVENT_ID))
        assert saved is not None
        assert saved.amount_minor == 150
        assert saved.currency == "XAF"
        assert saved.state == "pending_purchase_match"
        assert saved.external_reference == "ci-order"

        replay = client.post(ORIGIN, content=p, headers=signed(p))
        assert replay.status_code == 204
        conflicting = body(event_id=EVENT_ID, amount=200)
        assert client.post(ORIGIN, content=conflicting,
                           headers=signed(conflicting)).status_code == 409
        duplicate_effect = body(event_id=str(uuid.uuid4()), effect=EFFECT)
        dupe_id = json.loads(duplicate_effect)["eventId"]
        assert client.post(ORIGIN, content=duplicate_effect,
                           headers=signed(duplicate_effect, event_id=dupe_id)).status_code == 409

        os.environ["PRECIS_ORCHESTRATOR_EVENTS_ENVIRONMENT"] = "live"
        assert client.post(ORIGIN, content=p, headers=signed(p)).status_code == 503
        assert asyncio.run(persisted(EVENT_ID)) is not None
        print("OK signed, scoped, time-bound, durable and replay-safe; zero credits")
    finally:
        asyncio.run(cleanup())
        for key, original in snapshot.items():
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


if __name__ == "__main__":
    run()
