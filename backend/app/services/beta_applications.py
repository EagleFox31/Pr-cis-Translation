"""Public program information and private, reviewed applications."""
from sqlalchemy import select
from app.models import User
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
    occupied = await beta.capacity_used(db, campaign.id) if campaign else 0
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


async def for_user(db, user, campaign=None):
    campaign = campaign or await beta.campaign_row(db)
    if not campaign:
        return None
    return (await db.execute(select(BetaApplication).where(
        BetaApplication.campaign_id == campaign.id, BetaApplication.user_id == user.id,
        BetaApplication.email == user.email.strip().lower()))).scalar_one_or_none()


async def submit(db, user, *, primary_format, motivation, signals=None):
    if not user.email_verified:
        raise beta.error(403, "email_unverified", "Vérifiez votre adresse e-mail avant de déposer une candidature.")
    campaign = await beta.campaign_row(db, lock=True)
    existing = await for_user(db, user, campaign) if campaign else None
    if existing:
        return existing  # repeated clicks never create a second application
    if not campaign or not beta.recruitment_open(campaign):
        raise beta.error(409, "applications_closed", "Les candidatures à la bêta sont fermées.")
    if await beta.capacity_used(db, campaign.id) >= campaign.capacity:
        raise beta.error(409, "program_full", "Toutes les places du programme sont engagées.")
    latest = await beta.enrollment_for(db, user)
    if latest and latest.campaign_id == campaign.id:
        raise beta.error(409, "account_invited", "Une invitation existe déjà pour ce compte.")
    if await beta.access_running_elsewhere(db, user.email, campaign.id):
        raise beta.error(409, "previous_access_active", "Votre accès au programme précédent est encore en cours.")
    if await beta_abuse.mailbox_match(db, BetaEnrollment, user.email, campaign_id=campaign.id):
        raise beta.error(409, "mailbox_invited", "Une invitation existe déjà pour cette boîte e-mail.")
    if await beta_abuse.mailbox_match(db, BetaApplication, user.email, campaign_id=campaign.id):
        raise beta.error(409, "mailbox_applied", "Une candidature a déjà été déposée avec cette boîte e-mail.")
    await beta_abuse.check_submission_rate(db, signals, campaign_id=campaign.id)
    row = BetaApplication(campaign_id=campaign.id, user_id=user.id,
        email=user.email.strip().lower(), mailbox_key=beta_abuse.canonical_mailbox(user.email),
        primary_format=primary_format, motivation=motivation,
        ip_hash=signals.ip_hash if signals else None,
        device_hash=signals.device_hash if signals else None)
    db.add(row)
    await db.flush()
    return row


async def review(db, application_id, decision, admin):
    found = (await db.execute(select(BetaApplication.campaign_id).where(
        BetaApplication.id == application_id))).scalar_one_or_none()
    if not found:
        raise beta.error(404, "application_not_found", "Candidature introuvable.")
    # Same lock order as invitations: concurrent approvals share the seat cap.
    campaign = await beta.campaign_by_id(db, found, lock=True)
    row = (await db.execute(select(BetaApplication).where(BetaApplication.id == application_id)
        .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if row.state == decision:
        return row
    if row.state == "approved":
        raise beta.error(409, "application_reviewed", "Cette candidature a déjà été traitée.")
    if decision == "approved":
        if not row.user_id:
            raise beta.error(409, "candidate_deleted", "Le compte du candidat n'existe plus.")
        await beta.invite(db, email=row.email, primary_format=row.primary_format, reviewer_id=admin.id,
                          campaign=campaign)
        # Direct access: the candidate's own signals; a refusal waits for their next visit.
        candidate = await db.get(User, row.user_id)
        if candidate and candidate.email.strip().lower() == row.email:
            await beta.try_activate(db, candidate, signals=beta_abuse.ClientSignals(
                ip_hash=row.ip_hash, device_hash=row.device_hash))
    row.state = decision
    row.reviewed_at = beta.now_utc()
    row.reviewer_id = admin.id
    await db.flush()
    return row
