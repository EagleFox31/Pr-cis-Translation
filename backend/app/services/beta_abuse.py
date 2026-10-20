"""Beta mailbox deduplication and short-lived, admin-only abuse signals."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import ipaddress
import re
import secrets

from fastapi import HTTPException, Request, Response
from sqlalchemy import func, or_, select, update

from app.config import IS_PRODUCTION, JWT_SECRET
from app.models.beta import BetaApplication, BetaEnrollment

COOKIE_NAME = "precis_beta_device"
SIGNAL_DAYS = 30
WINDOW_SECONDS = 600
DEVICE_SUBMISSIONS = 5
IP_SUBMISSIONS = 20
_COOKIE = re.compile(r"[A-Za-z0-9_-]{32}\.[a-f0-9]{64}")


def canonical_mailbox(email: str) -> str:
    """A beta deduplication key, never a replacement for the login email.

    Gmail personal addresses ignore dots and +tags. Other domains, including
    Google Workspace custom domains, retain their original local part.
    """
    address = email.strip().casefold()
    local, separator, domain = address.rpartition("@")
    if separator and domain in ("gmail.com", "googlemail.com"):
        local = local.split("+", 1)[0].replace(".", "")
        return local + "@gmail.com"
    return address


def aware(value):
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def utcnow():
    return datetime.now(timezone.utc)


async def mailbox_match(db, model, email, *, exclude_id=None, activated_only=False):
    key = canonical_mailbox(email)
    query = select(model).where(model.campaign_id == "pilot",
        or_(model.mailbox_key == key, model.mailbox_key.is_(None)))
    if exclude_id is not None:
        query = query.where(model.id != exclude_id)
    if activated_only:
        query = query.where(model.activated_at.is_not(None))
    # NULL supports pre-existing/test rows without inventing identity metadata.
    rows = (await db.execute(query)).scalars().all()
    return next((row for row in rows if canonical_mailbox(row.email) == key), None)


def _digest(purpose: str, value: str) -> str:
    return hmac.new(JWT_SECRET.encode(), ("precis-beta:" + purpose + ":" + value).encode(),
                    hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class ClientSignals:
    ip_hash: str | None
    device_hash: str
    new_cookie: str | None = None


def client_signals(request: Request) -> ClientSignals:
    # The ASGI peer is resolved by the existing trusted deployment proxy.
    # Never accept client-supplied X-Forwarded-For / X-Real-IP here.
    peer = request.client.host if request.client else ""
    try:
        address = ipaddress.ip_address(peer).compressed
    except ValueError:
        address = None
    raw = request.cookies.get(COOKIE_NAME, "")
    valid = bool(_COOKIE.fullmatch(raw))
    if valid:
        nonce, signature = raw.split(".", 1)
        valid = hmac.compare_digest(signature, _digest("cookie", nonce))
    if not valid:
        nonce = secrets.token_urlsafe(24)
        raw = nonce + "." + _digest("cookie", nonce)
    return ClientSignals(
        ip_hash=_digest("ip", address) if address else None,
        device_hash=_digest("browser", nonce),
        new_cookie=None if valid else raw,
    )


def set_cookie(response: Response, signals: ClientSignals):
    response.headers["Cache-Control"] = "private, no-store"
    if signals.new_cookie:
        response.set_cookie(COOKIE_NAME, signals.new_cookie, max_age=SIGNAL_DAYS * 86400,
            path="/api/beta", secure=IS_PRODUCTION, httponly=True, samesite="lax")


async def check_submission_rate(db, signals: ClientSignals | None, *, now=None):
    """Campaign lock held by caller: concurrent admissions share the counters."""
    if signals is None:
        return
    cutoff = (now or utcnow()) - timedelta(seconds=WINDOW_SECONDS)
    for field, maximum in (("device_hash", DEVICE_SUBMISSIONS), ("ip_hash", IP_SUBMISSIONS)):
        value = getattr(signals, field)
        if value is None:
            continue
        count = (await db.execute(select(func.count()).select_from(BetaApplication).where(
            BetaApplication.campaign_id == "pilot", getattr(BetaApplication, field) == value,
            BetaApplication.submitted_at >= cutoff))).scalar() or 0
        if count >= maximum:
            raise HTTPException(429,
                "Plusieurs candidatures viennent d'être envoyées. Réessayez dans quelques minutes.",
                headers={"Retry-After": str(WINDOW_SECONDS)})


def admin_risks(applications, enrollments, *, now=None):
    """Related records are grouped by email: one's application + activation is one actor."""
    now = now or utcnow()
    cutoff = now - timedelta(days=SIGNAL_DAYS)
    recent_cutoff = now - timedelta(hours=1)
    entries = [("application", row, row.submitted_at) for row in applications]
    entries += [("enrollment", row, row.activated_at) for row in enrollments]
    groups = {kind: defaultdict(dict) for kind in ("same_mailbox", "same_ip", "same_browser")}
    recent = {kind: defaultdict(set) for kind in ("same_ip", "same_browser")}
    identities = {}
    for source, row, recorded_at in entries:
        email = row.email.strip().casefold()
        identities[email] = {"email": row.email}
        groups["same_mailbox"][canonical_mailbox(row.email)][email] = row.email
        if recorded_at is None or aware(recorded_at) < cutoff:
            continue
        for kind, field in (("same_ip", "ip_hash"), ("same_browser", "device_hash")):
            value = getattr(row, field, None)
            if value:
                groups[kind][value][email] = row.email
                if aware(recorded_at) >= recent_cutoff:
                    recent[kind][value].add(email)

    result = {}
    for source, row, recorded_at in entries:
        own_email = row.email.strip().casefold()
        flags, related, rapid = [], set(), set()
        keys = [("same_mailbox", canonical_mailbox(row.email))]
        if recorded_at is not None and aware(recorded_at) >= cutoff:
            keys += [("same_ip", row.ip_hash), ("same_browser", row.device_hash)]
        for kind, value in keys:
            if not value:
                continue
            others = set(groups[kind].get(value, {})) - {own_email}
            if others:
                flags.append({"kind": kind, "count": len(others)})
                related.update(others)
            if kind in recent:
                rapid.update(recent[kind].get(value, set()))
        if own_email in rapid and len(rapid) >= 3:
            flags.append({"kind": "rapid_sequence", "count": len(rapid)})
        result[(source, row.id)] = {
            "flags": flags, "related_count": len(related),
            "related": [identities[email] for email in sorted(related)[:10]],
        }
    return result


async def purge_signals(db, *, now=None):
    """Erase only expired network/browser digests; decisions, quotas and identity survive."""
    cutoff = (now or utcnow()) - timedelta(days=SIGNAL_DAYS)
    for model, timestamp in ((BetaApplication, BetaApplication.submitted_at),
                             (BetaEnrollment, BetaEnrollment.activated_at)):
        await db.execute(update(model).where(timestamp < cutoff,
            or_(model.ip_hash.is_not(None), model.device_hash.is_not(None)))
            .values(ip_hash=None, device_hash=None).execution_options(synchronize_session=False))


async def cleanup_loop():
    import asyncio
    import logging
    from app.core.database import async_session

    while True:
        try:
            async with async_session() as db:
                await purge_signals(db)
                await db.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.getLogger(__name__).exception("Bêta : purge des signaux expirés impossible")
        await asyncio.sleep(86400)
