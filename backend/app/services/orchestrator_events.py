"""Authenticité du protocole v1 Payment Orchestrator → Précis.

Pure module: no network, provider call, billing or credit side effect.
The HMAC covers the *exact HTTP body*, not a re-serialized JSON object.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from typing import Mapping

_REF = re.compile(r"^[A-Za-z0-9_:-]{1,160}$")
_KEY_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_SIGNATURE = re.compile(r"^v1=[0-9a-f]{64}$")
_MAX_BYTES = 8192
_MAX_DRIFT = 300


class InvalidOrchestratorEvent(ValueError):
    """Input is not authenticated, fresh or compatible with a purchase."""


@dataclass(frozen=True)
class VerifiedOrchestratorEvent:
    event_id: str
    effect_key: str
    project_id: str
    environment: str
    payment_id: str
    merchant_id: str
    external_reference: str
    provider_reference: str
    amount_minor: int
    currency: str
    digest: str


def _ref(value: object) -> bool:
    return isinstance(value, str) and bool(_REF.fullmatch(value))


def verify_orchestrator_event(
    headers: Mapping[str, str],
    body: bytes,
    *,
    secret: str,
    key_id: str,
    project_id: str,
    environment: str,
    now_seconds: int | None = None,
) -> VerifiedOrchestratorEvent:
    if len(secret) < 32 or not _KEY_ID.fullmatch(key_id):
        raise RuntimeError("Orchestrator event receiver requires a valid secret and key ID.")
    if environment not in ("sandbox", "live") or not _ref(project_id):
        raise RuntimeError("Orchestrator receiver environment or project is invalid.")
    if not body or len(body) > _MAX_BYTES:
        raise InvalidOrchestratorEvent("Invalid event size.")

    event_id = headers.get("x-trigenys-event-id", "")
    received_key_id = headers.get("x-trigenys-key-id", "")
    timestamp = headers.get("x-trigenys-timestamp", "")
    signature = headers.get("x-trigenys-signature", "")
    if (not _ref(event_id) or
            not _KEY_ID.fullmatch(received_key_id) or
            not hmac.compare_digest(received_key_id, key_id) or
            not timestamp.isascii() or not timestamp.isdecimal() or
            len(timestamp) > 12 or not _SIGNATURE.fullmatch(signature)):
        raise InvalidOrchestratorEvent("Invalid event authentication.")
    stamp = int(timestamp)
    now = int(time.time()) if now_seconds is None else now_seconds
    if abs(now - stamp) > _MAX_DRIFT:
        raise InvalidOrchestratorEvent("Event timestamp outside the replay window.")

    value = (
        b"v1\n" + timestamp.encode("ascii") + b"\n" +
        event_id.encode("ascii") + b"\n" + body
    )
    digest = hmac.new(secret.encode("utf-8"), value, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, "v1=" + digest):
        raise InvalidOrchestratorEvent("Invalid event signature.")

    try:
        event = json.loads(body)
    except (UnicodeDecodeError, ValueError) as exc:
        raise InvalidOrchestratorEvent("Malformed authenticated event.") from exc
    if not isinstance(event, dict) or not isinstance(event.get("data"), dict):
        raise InvalidOrchestratorEvent("Unexpected event structure.")
    data = event["data"]
    if (event.get("version") != 1 or
            event.get("type") != "payment.confirmed" or
            event.get("eventId") != event_id or
            event.get("environment") != environment or
            event.get("projectId") != project_id or
            not _ref(event.get("paymentId")) or
            not _ref(event.get("effectKey")) or
            data.get("eventType") != "payment.confirmed" or
            data.get("projectId") != project_id or
            data.get("paymentId") != event["paymentId"] or
            not _ref(data.get("merchantId")) or
            not _ref(data.get("externalReference")) or
            not _ref(data.get("providerReference")) or
            data.get("provider") != "fapshi" or
            data.get("currency") != "XAF" or
            type(data.get("amountMinor")) is not int or
            data["amountMinor"] < 100 or
            (data.get("environment") is not None and data["environment"] != environment) or
            set(data).intersection({"pages", "credits", "grant", "phone", "email", "userId"})):
        raise InvalidOrchestratorEvent("Invalid payment evidence.")

    return VerifiedOrchestratorEvent(
        event_id=event_id, effect_key=event["effectKey"],
        project_id=project_id, environment=environment,
        payment_id=event["paymentId"], merchant_id=data["merchantId"],
        external_reference=data["externalReference"],
        provider_reference=data["providerReference"],
        amount_minor=data["amountMinor"], currency="XAF",
        digest=hashlib.sha256(body).hexdigest(),
    )
