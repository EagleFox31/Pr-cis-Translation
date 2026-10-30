"""Manage beta programs and accept email-bound invitations."""
import unicodedata
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import require_admin, require_auth
from app.models import User
from app.models.beta import BetaApplication, BetaCampaign, BetaEnrollment
from app.rate_limit import rate_limit_decorator
from app.services import anti_abus, beta, beta_applications, beta_abuse
from app.services.usage import add_months

router = APIRouter(tags=["Bêta"])

_BIDI = set("\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")


class Limits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pdf: int = Field(20, ge=0, le=100_000)
    pptx: int = Field(20, ge=0, le=100_000)
    docx: int = Field(10_000, ge=0, le=1_000_000)
    xlsx: int = Field(10, ge=0, le=10_000)
    xlsx_words: int = Field(5_000, ge=0, le=1_000_000)


class CampaignSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field("Bêta Précis", min_length=1, max_length=120)
    capacity: int = Field(40, ge=1, le=1000)
    first_wave_capacity: int = Field(20, ge=1, le=1000)
    access_days: int = Field(30, ge=1, le=90)
    limits: Limits = Field(default_factory=Limits)

    @model_validator(mode="after")
    def waves_fit(self):
        if self.first_wave_capacity > self.capacity:
            raise ValueError("La première vague ne peut pas dépasser la capacité totale.")
        return self


class CampaignUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, min_length=1, max_length=120)
    capacity: int | None = Field(None, ge=1, le=1000)
    first_wave_capacity: int | None = Field(None, ge=1, le=1000)
    access_days: int | None = Field(None, ge=1, le=90)
    limits: Limits | None = None
    state: Literal["draft", "open", "closed"] | None = None


class Invitation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    primary_format: Literal["pdf", "pptx", "docx", "xlsx"] = "pdf"
    campaign_id: str | None = None


class EnrollmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limits: Limits | None = None
    revoke: bool | None = None


class ApplicationSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    primary_format: Literal["pdf", "pptx", "docx", "xlsx"]
    motivation: str = Field(min_length=10, max_length=1000)

    @field_validator("motivation")
    @classmethod
    def no_hidden_characters(cls, value: str) -> str:
        # Control and bidi characters could disguise the text an admin reviews.
        if any(char not in "\n\r\t" and (unicodedata.category(char) == "Cc" or char in _BIDI)
               for char in value):
            raise ValueError("La motivation contient des caractères invisibles.")
        return value


class ApplicationReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "declined"]


async def _signals(db, request):
    """Signaux anti-abus communs : l'appareil de la candidature est la machine
    reconnue par `anti_abus` (cookie, copie locale, empreinte)."""
    device = anti_abus.client_signals(request)
    machine_id, _known = await anti_abus.resolve_machine(db, device)
    return device, beta_abuse.ClientSignals(ip_hash=device.ip_hash, device_hash=machine_id)


@router.get("/api/beta/program")
@rate_limit_decorator("30/minute")
async def program(request: Request, db: AsyncSession = Depends(get_db)):
    return await beta_applications.public_program(db)


@router.post("/api/beta/applications")
# Above the 5-per-10-minutes admission burst, so its Retry-After stays visible.
@rate_limit_decorator("10/minute")
async def apply(body: ApplicationSubmission, request: Request, response: Response,
                user: User = Depends(require_auth), db: AsyncSession = Depends(get_db)):
    if anti_abus.is_disposable(user.email):
        raise beta.error(400, "disposable_email", anti_abus.DISPOSABLE_MESSAGE)
    device, signals = await _signals(db, request)
    row = await beta_applications.submit(db, user, signals=signals, **body.model_dump())
    await db.commit()
    anti_abus.set_cookie(response, device)
    return beta_applications.serialize(row)


@router.patch("/api/admin/beta/applications/{application_id}")
async def review(application_id: str, body: ApplicationReview,
                 admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    row = await beta_applications.review(db, application_id, body.decision, admin)
    await db.commit()
    return beta_applications.serialize(row)


async def _defaults(db):
    """A new program starts from the settings of the last one created."""
    last = (await db.execute(select(BetaCampaign).order_by(
        BetaCampaign.created_at.desc()).limit(1))).scalar_one_or_none()
    if not last:
        return CampaignSettings().model_dump()
    return CampaignSettings.model_validate(
        {key: getattr(last, key) for key in CampaignSettings.model_fields}).model_dump()


async def _campaigns(db):
    rows = (await db.execute(select(BetaCampaign).order_by(BetaCampaign.created_at.desc()))).scalars().all()
    return [await beta.serialize_campaign(db, row) for row in rows]


def _already_open():
    return beta.error(409, "campaign_already_open", "Un autre programme est déjà ouvert.")


def _recruitment_ended(campaign):
    return bool(campaign.recruitment_ends_at and beta.aware(campaign.recruitment_ends_at) <= beta.now_utc())


@router.get("/api/admin/beta")
async def dashboard(response: Response, campaign_id: str | None = None,
                    _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    campaign = await (beta.campaign_by_id(db, campaign_id) if campaign_id else beta.campaign_row(db))
    if campaign_id and not campaign:
        raise beta.error(404, "campaign_not_found", "Programme introuvable.")
    rows, applications = [], []
    if campaign:
        rows = (await db.execute(select(BetaEnrollment).where(
            BetaEnrollment.campaign_id == campaign.id).order_by(BetaEnrollment.invited_at.desc()))).scalars().all()
        applications = (await db.execute(select(BetaApplication).where(
            BetaApplication.campaign_id == campaign.id).order_by(BetaApplication.submitted_at.desc()))).scalars().all()
    risks = beta_abuse.admin_risks(applications, rows)
    return {"campaign": await beta.serialize_campaign(db, campaign),
            "campaigns": await _campaigns(db),
            "enrollments": [{**(await beta.serialize_enrollment(db, row)),
                "risk": risks[("enrollment", row.id)]} for row in rows],
            "applications": [{**beta_applications.serialize(row),
                "risk": risks[("application", row.id)]} for row in applications],
            "defaults": await _defaults(db)}


@router.get("/api/admin/beta/campaigns")
async def list_campaigns(response: Response, _admin: User = Depends(require_admin),
                         db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return {"campaigns": await _campaigns(db), "defaults": await _defaults(db)}


@router.post("/api/admin/beta/campaigns", status_code=201)
async def create_campaign(body: CampaignSettings, _admin: User = Depends(require_admin),
                          db: AsyncSession = Depends(get_db)):
    row = BetaCampaign(state="draft", **body.model_dump())
    db.add(row)
    await db.commit()
    return await beta.serialize_campaign(db, row)


@router.patch("/api/admin/beta/campaigns/{campaign_id}")
async def update_campaign(campaign_id: str, body: CampaignUpdate, _admin: User = Depends(require_admin),
                          db: AsyncSession = Depends(get_db)):
    updates = body.model_dump(exclude_unset=True, exclude_none=True)
    current = None
    if updates.get("state") == "open":
        # Serializes concurrent openings: the open program, if any, is locked first.
        current = await beta.campaign_row(db, lock=True)
        if current and (current.state != "open" or current.id == campaign_id):
            current = None
        elif current and not _recruitment_ended(current):
            raise _already_open()
    row = await beta.campaign_by_id(db, campaign_id, lock=True)
    if not row:
        raise beta.error(404, "campaign_not_found", "Programme introuvable.")
    if updates.get("state") == "open" and row.state != "open" and _recruitment_ended(row):
        raise beta.error(409, "campaign_recruitment_ended", "La période de recrutement de ce programme est terminée.")
    state = updates.pop("state", row.state)
    try:
        settings = CampaignSettings.model_validate({
            **{key: getattr(row, key) for key in CampaignSettings.model_fields}, **updates,
        })
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_context=False))
    if row.starts_at and state == "draft":
        raise beta.error(409, "campaign_reopen_draft", "Un programme ouvert ne peut pas revenir en brouillon.")
    if settings.capacity < await beta.capacity_used(db, row.id):
        raise beta.error(409, "capacity_below_used", "La capacité ne peut pas être inférieure aux places déjà engagées.")
    for key, value in settings.model_dump().items():
        setattr(row, key, value)
    if current:
        # An open program whose recruitment has ended no longer holds the single open slot.
        current.state = "closed"
        await db.flush()
    row.state = state
    if row.state == "open" and row.starts_at is None:
        row.starts_at = beta.now_utc()
        row.recruitment_ends_at = add_months(row.starts_at, 2)
    # Reopening never resets enrollment dates, consumed quotas or access clocks.
    try:
        await db.commit()
    except IntegrityError:
        # The partial unique index settles openings that raced past the lock.
        await db.rollback()
        raise _already_open()
    return await beta.serialize_campaign(db, row)


@router.post("/api/admin/beta/invitations", status_code=201)
async def invite(body: Invitation, _admin: User = Depends(require_admin),
                 db: AsyncSession = Depends(get_db)):
    campaign = None
    if body.campaign_id:
        # The admin invites into the program on screen, never into whichever one is open now.
        campaign = await beta.campaign_by_id(db, body.campaign_id, lock=True)
        if not campaign:
            raise beta.error(404, "campaign_not_found", "Programme introuvable.")
    row = await beta.invite(db, email=str(body.email), primary_format=body.primary_format,
                            reviewer_id=_admin.id, campaign=campaign)
    await db.commit()
    return await beta.serialize_enrollment(db, row)


@router.patch("/api/admin/beta/enrollments/{enrollment_id}")
async def update_enrollment(enrollment_id: str, body: EnrollmentUpdate,
                            _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    found = await beta.enrollment_by_id(db, enrollment_id)
    if not found:
        raise beta.error(404, "enrollment_not_found", "Invitation introuvable.")
    campaign = await beta.campaign_by_id(db, found.campaign_id, lock=True)
    row = await beta.enrollment_by_id(db, enrollment_id, lock=True)
    if body.limits is not None:
        row.limits = body.limits.model_dump()
    if body.revoke and row.revoked_at is None:
        row.revoked_at = beta.now_utc()
    elif body.revoke is False and row.revoked_at:
        if await beta_abuse.mailbox_match(db, BetaEnrollment, row.email, campaign_id=row.campaign_id,
                exclude_id=row.id, activated_only=True):
            raise beta.error(409, "mailbox_used", "Cette boîte e-mail a déjà bénéficié de la bêta.")
        if await beta.access_running_elsewhere(db, row.email, row.campaign_id):
            raise beta.error(409, "previous_access_active", "L'accès à un programme précédent est encore en cours.")
        if row.activated_at is None and (
                not campaign or not beta.recruitment_open(campaign)
                or await beta.capacity_used(db, campaign.id) >= beta.wave_capacity(campaign)):
            raise beta.error(409, "no_seat_to_restore", "Aucune place disponible pour rétablir cette invitation.")
        row.revoked_at = None
    await db.commit()
    return await beta.serialize_enrollment(db, row)


@router.get("/api/beta/me")
async def me(request: Request, response: Response, user: User = Depends(require_auth),
             db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    row = await beta.enrollment_for(db, user)
    if row and row.activated_at is None and not row.revoked_at:
        # Accès direct : l'invitation s'active à la première lecture du statut ;
        # un refus (e-mail non vérifié, programme fermé…) la laisse en attente.
        device, signals = await _signals(db, request)
        if await beta.try_activate(db, user, signals=signals):
            try:
                await db.commit()
                anti_abus.set_cookie(response, device)
            except IntegrityError:
                await db.rollback()  # activation simultanée de la même boîte : l'autre l'emporte
            row = await beta.enrollment_for(db, user)
    if row and row.activated_at and row.user_id != user.id:
        row = None
    campaign = await beta.campaign_row(db)
    if (row and campaign and row.campaign_id != campaign.id and beta.enrollment_state(row) != "active"
            and beta.recruitment_open(campaign)):
        row = None  # a finished earlier access gives way to the open program's application form
    application = await beta_applications.for_user(db, user, campaign) if campaign else None
    # Name and duration follow the invitation's own program, not the most recent one.
    source = await beta.campaign_by_id(db, row.campaign_id) if row else campaign
    return {"enrollment": await beta.serialize_enrollment(db, row) if row else None,
            "application": beta_applications.serialize(application) if application else None,
            "campaign_name": source.name if source else None,
            "access_days": source.access_days if source else None,
            "can_activate": bool(row and row.activated_at is None and not row.revoked_at
                                 and source and beta.recruitment_open(source)),
            "email_verified": user.email_verified}


@router.post("/api/beta/activate")
@rate_limit_decorator("5/minute")
async def activate(request: Request, response: Response, user: User = Depends(require_auth),
                   db: AsyncSession = Depends(get_db)):
    device, signals = await _signals(db, request)
    try:
        row = await beta.activate(db, user, signals=signals)
        await db.commit()
    except IntegrityError:
        # Deux activations simultanées de la même boîte : l'index unique tranche
        # (au flush d'`activate` ou au commit).
        await db.rollback()
        raise beta.error(409, "mailbox_used", "Cette boîte e-mail a déjà bénéficié de la bêta.")
    anti_abus.set_cookie(response, device)
    return await beta.serialize_enrollment(db, row)
