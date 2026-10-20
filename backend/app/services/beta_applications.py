"""Public program information and private, reviewed applications."""
from fastapi import HTTPException
from sqlalchemy import select
from app.models.beta import BetaApplication, BetaEnrollment
from app.services import beta, beta_abuse
from app.services.beta_meter import DEFAULT_LIMITS


def serialize(row):
    return {
        "id": row.id, "email": row.email, "primary_format": row.primary_format,
        "motivation": row.motivation, "state": row.state,
        "submitted_at": beta.aware(row.submitted_at).isoformat(),
        "reviewed_at": beta.aware(row.reviewed_at).isoformat() if row.reviewed_at else None,
    }


async def public_program(db):
    campaign = await beta.campaign_row(db)
    occupied = await beta.capacity_used(db) if campaign else 0
    available = bool(campaign and beta.recruitment_open(campaign))
    ended = bool(campaign and campaign.recruitment_ends_at
                 and beta.aware(campaign.recruitment_ends_at) <= beta.now_utc())
    full = bool(campaign and occupied >= campaign.capacity)
    return {
        "name": campaign.name if campaign else "Bêta Précis",
        "capacity": campaign.capacity if campaign else 40,
        "first_wave_capacity": campaign.first_wave_capacity if campaign else 20,
        "access_days": campaign.access_days if campaign else 30,
        "limits": {**DEFAULT_LIMITS, **(campaign.limits if campaign else {})},
        "availability": "ended" if ended else "full" if full else "open" if available else "closed",
        "applications_open": available and not full,
    }


async def for_user(db, user):
    return (await db.execute(select(BetaApplication).where(
        BetaApplication.campaign_id == "pilot", BetaApplication.user_id == user.id,
        BetaApplication.email == user.email.strip().casefold()))).scalar_one_or_none()


async def submit(db, user, *, primary_format, motivation, signals=None):
    if not user.email_verified:
        raise HTTPException(403, "Vérifiez votre adresse e-mail avant de déposer une candidature.")
    campaign = await beta.campaign_row(db, lock=True)
    existing = await for_user(db, user)
    if existing:
        return existing  # repeated clicks never create a second application
    if not campaign or not beta.recruitment_open(campaign):
        raise HTTPException(409, "Les candidatures à la bêta sont fermées.")
    if await beta.capacity_used(db) >= campaign.capacity:
        raise HTTPException(409, "Toutes les places du programme sont engagées.")
    if await beta.enrollment_for(db, user):
        raise HTTPException(409, "Une invitation existe déjà pour ce compte.")
    if await beta_abuse.mailbox_match(db, BetaEnrollment, user.email):
        raise HTTPException(409, "Une invitation existe déjà pour cette boîte e-mail.")
    if await beta_abuse.mailbox_match(db, BetaApplication, user.email):
        raise HTTPException(409, "Une candidature a déjà été déposée avec cette boîte e-mail.")
    await beta_abuse.check_submission_rate(db, signals)
    row = BetaApplication(campaign_id="pilot", user_id=user.id,
        email=user.email.strip().casefold(), mailbox_key=beta_abuse.canonical_mailbox(user.email),
        primary_format=primary_format, motivation=motivation,
        ip_hash=signals.ip_hash if signals else None,
        device_hash=signals.device_hash if signals else None)
    db.add(row)
    await db.flush()
    return row


async def review(db, application_id, decision, admin):
    # Same lock order as invitations: concurrent approvals share the seat cap.
    await beta.campaign_row(db, lock=True)
    row = (await db.execute(select(BetaApplication).where(BetaApplication.id == application_id)
        .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Candidature introuvable.")
    if row.state == decision:
        return row
    if row.state == "approved":
        raise HTTPException(409, "Cette candidature a déjà été traitée.")
    if decision == "approved":
        if not row.user_id:
            raise HTTPException(409, "Le compte du candidat n'existe plus.")
        await beta.invite(db, email=row.email, primary_format=row.primary_format, reviewer_id=admin.id)
    row.state = decision
    row.reviewed_at = beta.now_utc()
    row.reviewer_id = admin.id
    await db.flush()
    return row
