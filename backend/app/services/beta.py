"""Authoritative beta invitations, admission windows and per-format allowances."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import func, or_, select
from app.models import User
from app.models.beta import BetaApplication, BetaCampaign, BetaEnrollment, BetaUsage
from app.services.beta_meter import BetaCost, DEFAULT_LIMITS, FORMATS, UNIT_NAMES
from app.services.usage import add_months
from app.services import beta_abuse


def now_utc():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def recruitment_open(campaign, now=None):
    now = now or now_utc()
    return bool(campaign.state == "open" and campaign.starts_at and campaign.recruitment_ends_at
                and aware(campaign.starts_at) <= now < aware(campaign.recruitment_ends_at))


def wave_capacity(campaign, now=None):
    now = now or now_utc()
    if not campaign.starts_at or now < add_months(aware(campaign.starts_at), 1):
        return min(campaign.capacity, campaign.first_wave_capacity)
    return campaign.capacity


def enrollment_state(enrollment, now=None):
    now = now or now_utc()
    if enrollment.revoked_at:
        return "revoked"
    if enrollment.activated_at is None:
        return "invited"
    if not enrollment.expires_at or aware(enrollment.expires_at) <= now:
        return "expired"
    return "active"


async def campaign_row(db, *, lock=False):
    query = select(BetaCampaign).where(BetaCampaign.id == "pilot")
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return (await db.execute(query)).scalar_one_or_none()


async def enrollment_for(db, user, *, lock=False):
    query = select(BetaEnrollment).where(
        BetaEnrollment.campaign_id == "pilot",
        BetaEnrollment.email == user.email.strip().casefold())
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return (await db.execute(query)).scalar_one_or_none()


async def totals(db, enrollment_id):
    rows = (await db.execute(
        select(BetaUsage.format, func.sum(BetaUsage.units), func.sum(BetaUsage.words))
        .where(BetaUsage.enrollment_id == enrollment_id, BetaUsage.refunded.is_(False))
        .group_by(BetaUsage.format))).all()
    return {fmt: {"units": int(units or 0), "words": int(words or 0)}
            for fmt, units, words in rows}


async def serialize_enrollment(db, enrollment, *, now=None):
    used = await totals(db, enrollment.id)
    limits = {**DEFAULT_LIMITS, **enrollment.limits}
    return {
        "id": enrollment.id, "email": enrollment.email,
        "primary_format": enrollment.primary_format,
        "state": enrollment_state(enrollment, now),
        "invited_at": aware(enrollment.invited_at).isoformat(),
        "activated_at": aware(enrollment.activated_at).isoformat() if enrollment.activated_at else None,
        "expires_at": aware(enrollment.expires_at).isoformat() if enrollment.expires_at else None,
        "limits": limits,
        "formats": {
            fmt: {
                "unit": UNIT_NAMES[fmt], "limit": limits[fmt],
                "used": used.get(fmt, {}).get("units", 0),
                "remaining": max(0, limits[fmt] - used.get(fmt, {}).get("units", 0)),
                **({"word_limit": limits["xlsx_words"],
                    "words_used": used.get(fmt, {}).get("words", 0),
                    "words_remaining": max(0, limits["xlsx_words"] - used.get(fmt, {}).get("words", 0))}
                   if fmt == "xlsx" else {}),
            } for fmt in FORMATS
        },
    }


async def capacity_used(db):
    # Activated seats remain counted after expiry, revocation and account
    # deletion. Only a never-activated revoked invitation frees a seat.
    return int((await db.execute(
        select(func.count()).select_from(BetaEnrollment).where(
            BetaEnrollment.campaign_id == "pilot",
            or_(BetaEnrollment.activated_at.is_not(None), BetaEnrollment.revoked_at.is_(None))
        ))).scalar() or 0)


async def serialize_campaign(db, campaign):
    if not campaign:
        return None
    return {
        "id": campaign.id, "name": campaign.name, "state": campaign.state,
        "capacity": campaign.capacity, "first_wave_capacity": campaign.first_wave_capacity,
        "current_capacity": wave_capacity(campaign), "seats_used": await capacity_used(db),
        "access_days": campaign.access_days, "limits": campaign.limits,
        "starts_at": aware(campaign.starts_at).isoformat() if campaign.starts_at else None,
        "recruitment_ends_at": aware(campaign.recruitment_ends_at).isoformat() if campaign.recruitment_ends_at else None,
        "second_wave_at": add_months(aware(campaign.starts_at), 1).isoformat() if campaign.starts_at else None,
        "recruitment_open": recruitment_open(campaign),
    }


async def invite(db, *, email, primary_format, limits=None, reviewer_id=None):
    campaign = await campaign_row(db, lock=True)
    if not campaign or not recruitment_open(campaign):
        raise HTTPException(409, "Les inscriptions à la bêta sont fermées.")
    if await capacity_used(db) >= wave_capacity(campaign):
        raise HTTPException(409, "La capacité de cette vague est atteinte.")
    email = email.strip().casefold()
    existing = await beta_abuse.mailbox_match(db, BetaEnrollment, email)
    if existing:
        raise HTTPException(409, "Cette boîte e-mail possède déjà une invitation à cette campagne.")
    item = BetaEnrollment(campaign_id="pilot", email=email, mailbox_key=beta_abuse.canonical_mailbox(email),
                          primary_format=primary_format,
                          limits=dict(limits or campaign.limits))
    db.add(item)
    await db.flush()
    # A manual invitation also resolves the matching pending application.
    application = (await db.execute(select(BetaApplication).where(
        BetaApplication.campaign_id == "pilot", BetaApplication.email == email,
        BetaApplication.state.in_(("pending", "declined"))))).scalar_one_or_none()
    if application:
        application.state = "approved"
        application.reviewed_at = now_utc()
        application.reviewer_id = reviewer_id
    return item


async def activate(db, user, *, signals=None):
    if not user.email_verified:
        raise HTTPException(403, "Vérifiez votre adresse e-mail avant d'activer la bêta.")
    campaign = await campaign_row(db, lock=True)
    if not campaign:
        raise HTTPException(404, "Aucune invitation bêta.")
    enrollment = await enrollment_for(db, user, lock=True)
    if enrollment is None or enrollment.revoked_at:
        raise HTTPException(404, "Aucune invitation bêta.")
    if enrollment.activated_at is not None:
        if enrollment.user_id != user.id:
            raise HTTPException(409, "Cette invitation a déjà été utilisée.")
        return enrollment
    if not recruitment_open(campaign):
        raise HTTPException(409, "La période d'activation est terminée.")
    if await beta_abuse.mailbox_match(db, BetaEnrollment, user.email,
            exclude_id=enrollment.id, activated_only=True):
        raise HTTPException(409, "Cette boîte e-mail a déjà bénéficié de la bêta.")
    enrollment.user_id = user.id
    enrollment.mailbox_key = beta_abuse.canonical_mailbox(user.email)
    enrollment.ip_hash = signals.ip_hash if signals else None
    enrollment.device_hash = signals.device_hash if signals else None
    enrollment.activated_at = now_utc()
    enrollment.expires_at = enrollment.activated_at + timedelta(days=campaign.access_days)
    await db.flush()
    return enrollment


async def active_enrollment(db, user, *, lock=False):
    item = await enrollment_for(db, user, lock=lock)
    if item and item.user_id == user.id and enrollment_state(item) == "active":
        return item
    return None


async def check_cost(db, enrollment, cost):
    used = await totals(db, enrollment.id)
    limits = {**DEFAULT_LIMITS, **enrollment.limits}
    previous = used.get(cost.format, {})
    remaining = max(0, limits[cost.format] - previous.get("units", 0))
    words_remaining = max(0, limits["xlsx_words"] - previous.get("words", 0))
    if cost.units > remaining or (cost.format == "xlsx" and cost.words > words_remaining):
        raise HTTPException(402, {
            "reason": "beta_quota", "format": cost.format, "unit": UNIT_NAMES[cost.format],
            "required": cost.units, "remaining": remaining,
            "words_required": cost.words, "words_remaining": words_remaining if cost.format == "xlsx" else None,
            "message": "Le quota bêta de ce format ne couvre pas ce document. "
                       "Sélectionnez moins de pages ou utilisez votre forfait habituel.",
        })


def record(db, enrollment_id, document_id, cost):
    db.add(BetaUsage(enrollment_id=enrollment_id, document_id=document_id, document_key=document_id,
                     format=cost.format, units=cost.units, words=cost.words))


async def refund_for_document(db, document_id, *, refunded=True):
    ids = (await db.execute(select(BetaUsage.enrollment_id).where(
        BetaUsage.document_key == document_id))).scalars().all()
    for enrollment_id in sorted(set(ids)):
        # Serializes refunds/rebilling with concurrent quota admission.
        await db.execute(select(BetaEnrollment).where(BetaEnrollment.id == enrollment_id).with_for_update())
    rows = (await db.execute(select(BetaUsage).where(
        BetaUsage.document_key == document_id, BetaUsage.refunded.is_(not refunded))
        .with_for_update().execution_options(populate_existing=True))).scalars().all()
    for row in rows:
        row.refunded = refunded
