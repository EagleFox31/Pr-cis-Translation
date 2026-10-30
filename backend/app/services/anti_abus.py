"""Anti-abus des pages offertes : appareil, boîte e-mail, vélocité IP.

PRINCIPE (cf. docs/etude-anti-abus.md, § 5 et § 7)
    Le quota reste PAR COMPTE. Ce module ne bloque jamais un compte : il décide
    seulement si les pages OFFERTES peuvent être servies. Les pages achetées
    restent toujours utilisables.

    Un appareil est reconnu par trois identifiants (cookie signé, copie locale,
    empreinte navigateur), tous hachés en HMAC avant usage. Les deux derniers
    viennent d'en-têtes falsifiables : ils ne servent donc qu'à RELIER des
    identifiants à une même machine, jamais à les délier.

    Abus net (refus sans appel) : domaine e-mail jetable, même boîte canonique
    déjà servie à un autre compte ce mois-ci.
    Zone grise (levée par un téléphone vérifié) : machine déjà servie à
    plusieurs autres comptes, vélocité IP, compte neuf sur appareil inconnu.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import logging
import re
import secrets

from disposable_email_domains import blocklist as _BLOCKLIST
from fastapi import HTTPException, Request, Response
from sqlalchemy import delete, func, select, update

from app.config import IS_PRODUCTION, JWT_SECRET
from app.models import DeviceLink, FreeGrant, User
from app.models.base import new_uuid
from app.services import usage
from app.services.beta_abuse import aware, canonical_mailbox, network_key

logger = logging.getLogger(__name__)

COOKIE_NAME = "precis_device"
COOKIE_DAYS = 365
LINK_DAYS = 60
GRANT_DAYS = 35
MACHINE_OTHER_ACCOUNTS = 2
IP_PAGES_24H = 30
NEW_ACCOUNT_HOURS = 24

_COOKIE = re.compile(r"[A-Za-z0-9_-]{32}\.[a-f0-9]{64}")
_HEADER = re.compile(r"[A-Za-z0-9_-]{8,128}")

# Domaines jetables propres au projet, en plus de la liste publique.
EXTRA_DISPOSABLE: frozenset[str] = frozenset()
# Exceptions locales : jamais considérés comme jetables.
ALLOWLIST_EXTRA: frozenset[str] = frozenset()
# Jamais considérés comme jetables, même si la liste publique les contenait.
ALLOWLIST: frozenset[str] = frozenset({"gmail.com", "googlemail.com"}) | ALLOWLIST_EXTRA

DISPOSABLE_MESSAGE = "Les adresses e-mail temporaires ne sont pas acceptées."


def utcnow():
    return datetime.now(timezone.utc)


def _digest(purpose: str, value: str) -> str:
    return hmac.new(JWT_SECRET.encode(), ("precis-abuse:" + purpose + ":" + value).encode(),
                    hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class DeviceSignals:
    ip_hash: str | None
    cookie_hash: str
    copy_hash: str | None
    print_hash: str | None
    new_cookie: str | None = None


def _header_hash(request: Request, name: str, purpose: str) -> str | None:
    raw = request.headers.get(name, "")
    return _digest(purpose, raw) if _HEADER.fullmatch(raw) else None


def client_signals(request: Request) -> DeviceSignals:
    # Le pair ASGI est résolu par le proxy de déploiement de confiance : on ne
    # lit jamais X-Forwarded-For / X-Real-IP, falsifiables par le client.
    peer = request.client.host if request.client else ""
    address = network_key(peer)
    raw = request.cookies.get(COOKIE_NAME, "")
    valid = bool(_COOKIE.fullmatch(raw))
    if valid:
        nonce, signature = raw.split(".", 1)
        valid = hmac.compare_digest(signature, _digest("cookie-signature", nonce))
    if not valid:
        nonce = secrets.token_urlsafe(24)
        raw = nonce + "." + _digest("cookie-signature", nonce)
    return DeviceSignals(
        ip_hash=_digest("ip", address) if address else None,
        cookie_hash=_digest("cookie", nonce),
        copy_hash=_header_hash(request, "x-device-copy", "copy"),
        print_hash=_header_hash(request, "x-device-print", "print"),
        new_cookie=None if valid else raw,
    )


def set_cookie(response: Response, signals: DeviceSignals):
    response.headers["Cache-Control"] = "private, no-store"
    if signals.new_cookie:
        response.set_cookie(COOKIE_NAME, signals.new_cookie, max_age=COOKIE_DAYS * 86400,
            path="/api", secure=IS_PRODUCTION, httponly=True, samesite="lax")


def _insert_ignore(db, values: dict):
    """INSERT qui ignore un doublon de `hash` (deux requêtes simultanées du même appareil)."""
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        from sqlalchemy import insert
    statement = insert(DeviceLink).values(**values)
    if hasattr(statement, "on_conflict_do_nothing"):
        statement = statement.on_conflict_do_nothing(index_elements=["hash"])
    return db.execute(statement)


async def resolve_machine(db, signals: DeviceSignals, now=None) -> tuple[str, bool]:
    """(machine_id, connue). L'appelant valide la transaction.

    Fusion : si les identifiants FORTS présents (cookie, copie locale, tirés au
    hasard) relèvent de plusieurs machines, la plus ancienne l'emporte et les
    autres lui sont rattachées (liens et attributions). L'empreinte, sujette aux
    collisions (appareils identiques), ne fusionne jamais : elle ne rattache un
    navigateur que s'il n'apporte aucun identifiant fort déjà connu (cookie et
    stockage effacés). Les en-têtes servent seulement à relier, jamais à délier."""
    now = now or utcnow()
    hashes = {kind: value for kind, value in (
        ("cookie", signals.cookie_hash), ("copy", signals.copy_hash),
        ("print", signals.print_hash)) if value}
    rows = (await db.execute(select(DeviceLink).where(
        DeviceLink.hash.in_(list(hashes.values()))))).scalars().all()
    strong = [row for row in rows if row.kind != "print"]
    if strong:
        rows = strong
    if rows:
        oldest = min(rows, key=lambda row: (aware(row.created_at), row.id))
        machine_id, known = oldest.machine_id, True
        merged = {row.machine_id for row in rows} - {machine_id}
        if merged:
            for model in (DeviceLink, FreeGrant):
                await db.execute(update(model).where(model.machine_id.in_(merged))
                    .values(machine_id=machine_id).execution_options(synchronize_session=False))
    else:
        machine_id, known = new_uuid(), False
    present = {row.hash for row in rows}
    for kind, value in hashes.items():
        if value not in present:
            await _insert_ignore(db, {"id": new_uuid(), "hash": value, "kind": kind,
                "machine_id": machine_id, "created_at": now, "last_seen": now})
    if present:
        await db.execute(update(DeviceLink).where(DeviceLink.hash.in_(list(present)))
            .values(last_seen=now).execution_options(synchronize_session=False))
    return machine_id, known


def is_disposable(email: str) -> bool:
    domain = email.strip().lower().rpartition("@")[2].strip(".")
    labels = domain.split(".")
    # Le domaine et ses parents, sans le suffixe seul : `x.mailinator.com`
    # est jetable parce que `mailinator.com` l'est.
    chain = [".".join(labels[i:]) for i in range(max(len(labels) - 1, 1))]
    if not domain or any(name in ALLOWLIST for name in chain):
        return False
    return any(name in _BLOCKLIST or name in EXTRA_DISPOSABLE for name in chain)


def reject_disposable(email: str):
    if is_disposable(email):
        raise HTTPException(400, DISPOSABLE_MESSAGE)


def mailbox_key(email: str) -> str:
    return _digest("mailbox", canonical_mailbox(email))


async def free_risk(db, user, signals: DeviceSignals, machine_id: str, known: bool,
                    needed: int, now=None) -> str | None:
    """Raison de refus des pages OFFERTES, ou None. Appelé sous le verrou du compte."""
    now = aware(now or utcnow())
    if is_disposable(user.email):
        return "disposable"
    month = usage.month_start(now)
    other_mailbox = await db.scalar(select(func.count()).select_from(FreeGrant).where(
        FreeGrant.user_id != user.id, FreeGrant.mailbox_key == mailbox_key(user.email),
        FreeGrant.created_at >= month))
    if other_mailbox:
        return "mailbox"
    if user.phone_verified_at is not None:
        return None
    accounts = await db.scalar(select(func.count(func.distinct(FreeGrant.user_id))).where(
        FreeGrant.machine_id == machine_id, FreeGrant.user_id != user.id,
        FreeGrant.created_at >= month))
    if (accounts or 0) >= MACHINE_OTHER_ACCOUNTS:
        return "device"
    if signals.ip_hash:
        recent = await db.scalar(select(func.coalesce(func.sum(FreeGrant.pages), 0)).where(
            FreeGrant.ip_hash == signals.ip_hash,
            FreeGrant.created_at >= now - timedelta(hours=24)))
        if (recent or 0) + needed > IP_PAGES_24H:
            return "ip"
    if (user.created_at is not None
            and aware(user.created_at) > now - timedelta(hours=NEW_ACCOUNT_HOURS)
            and not known):
        return "new_account"
    return None


def record_grant(db, user, signals: DeviceSignals, machine_id: str, pages: int, now=None):
    db.add(FreeGrant(user_id=user.id, machine_id=machine_id, ip_hash=signals.ip_hash,
                     mailbox_key=mailbox_key(user.email), pages=pages,
                     created_at=now or utcnow()))


async def purge(db, now=None):
    """Efface les liens inactifs depuis 60 jours et les attributions de plus de 35 jours."""
    now = now or utcnow()
    await db.execute(delete(DeviceLink).where(
        DeviceLink.last_seen < now - timedelta(days=LINK_DAYS)))
    await db.execute(delete(FreeGrant).where(
        FreeGrant.created_at < now - timedelta(days=GRANT_DAYS)))


async def touch(db, request: Request, response: Response):
    """Enregistre l'appareil dès l'inscription, pour qu'il soit « connu » ensuite.
    Ne lève jamais : un échec ici ne doit pas empêcher de se connecter."""
    try:
        signals = client_signals(request)
        await resolve_machine(db, signals)
        await db.commit()
        set_cookie(response, signals)
    except Exception:
        logger.exception("Anti-abus : enregistrement de l'appareil impossible")
        try:
            await db.rollback()
        except Exception:
            pass
