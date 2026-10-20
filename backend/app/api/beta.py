"""Manage the closed pilot and accept email-bound invitations."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import require_admin, require_auth
from app.models import User
from app.models.beta import BetaApplication, BetaCampaign, BetaEnrollment
from app.services import beta, beta_applications
from app.services.usage import add_months

router = APIRouter(tags=["Bêta"])


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


class EnrollmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limits: Limits | None = None
    revoke: bool | None = None


class ApplicationSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    primary_format: Literal["pdf", "pptx", "docx", "xlsx"]
    motivation: str = Field(min_length=10, max_length=1000)


class ApplicationReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "declined"]


@router.get("/api/beta/program")
async def program(db: AsyncSession = Depends(get_db)):
    return await beta_applications.public_program(db)


@router.post("/api/beta/applications")
async def apply(body: ApplicationSubmission, user: User = Depends(require_auth),
                db: AsyncSession = Depends(get_db)):
    row = await beta_applications.submit(db, user, **body.model_dump())
    await db.commit()
    return beta_applications.serialize(row)


@router.patch("/api/admin/beta/applications/{application_id}")
async def review(application_id: str, body: ApplicationReview,
                 admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    row = await beta_applications.review(db, application_id, body.decision, admin)
    await db.commit()
    return beta_applications.serialize(row)


@router.get("/api/admin/beta")
async def dashboard(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    campaign = await beta.campaign_row(db)
    rows = (await db.execute(select(BetaEnrollment).where(
        BetaEnrollment.campaign_id == "pilot").order_by(BetaEnrollment.invited_at.desc()))).scalars().all()
    applications = (await db.execute(select(BetaApplication).where(
        BetaApplication.campaign_id == "pilot").order_by(BetaApplication.submitted_at.desc()))).scalars().all()
    return {"campaign": await beta.serialize_campaign(db, campaign),
            "enrollments": [await beta.serialize_enrollment(db, row) for row in rows],
            "applications": [beta_applications.serialize(row) for row in applications],
            "defaults": CampaignSettings().model_dump()}


@router.post("/api/admin/beta/campaign", status_code=201)
async def create_campaign(body: CampaignSettings, _admin: User = Depends(require_admin),
                          db: AsyncSession = Depends(get_db)):
    if await beta.campaign_row(db):
        raise HTTPException(409, "Le programme existe déjà.")
    row = BetaCampaign(id="pilot", state="draft", **body.model_dump())
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Le programme existe déjà.")
    return await beta.serialize_campaign(db, row)


@router.patch("/api/admin/beta/campaign")
async def update_campaign(body: CampaignUpdate, _admin: User = Depends(require_admin),
                          db: AsyncSession = Depends(get_db)):
    row = await beta.campaign_row(db, lock=True)
    if not row:
        raise HTTPException(404, "Programme introuvable.")
    updates = body.model_dump(exclude_unset=True, exclude_none=True)
    state = updates.pop("state", row.state)
    try:
        settings = CampaignSettings.model_validate({
            **{key: getattr(row, key) for key in CampaignSettings.model_fields}, **updates,
        })
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_context=False))
    if row.starts_at and state == "draft":
        raise HTTPException(409, "Un programme ouvert ne peut pas revenir en brouillon.")
    if settings.capacity < await beta.capacity_used(db):
        raise HTTPException(409, "La capacité ne peut pas être inférieure aux places déjà engagées.")
    for key, value in settings.model_dump().items():
        setattr(row, key, value)
    row.state = state
    if row.state == "open" and row.starts_at is None:
        row.starts_at = beta.now_utc()
        row.recruitment_ends_at = add_months(row.starts_at, 2)
    # Reopening never resets enrollment dates, consumed quotas or access clocks.
    await db.commit()
    return await beta.serialize_campaign(db, row)


@router.post("/api/admin/beta/invitations", status_code=201)
async def invite(body: Invitation, _admin: User = Depends(require_admin),
                 db: AsyncSession = Depends(get_db)):
    row = await beta.invite(db, email=str(body.email), primary_format=body.primary_format, reviewer_id=_admin.id)
    await db.commit()
    return await beta.serialize_enrollment(db, row)


@router.patch("/api/admin/beta/enrollments/{enrollment_id}")
async def update_enrollment(enrollment_id: str, body: EnrollmentUpdate,
                            _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    campaign = await beta.campaign_row(db, lock=True)
    row = (await db.execute(select(BetaEnrollment).where(
        BetaEnrollment.id == enrollment_id).with_for_update()
        .execution_options(populate_existing=True))).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Invitation introuvable.")
    if body.limits is not None:
        row.limits = body.limits.model_dump()
    if body.revoke and row.revoked_at is None:
        row.revoked_at = beta.now_utc()
    elif body.revoke is False and row.revoked_at:
        if row.activated_at is None and (
                not campaign or not beta.recruitment_open(campaign)
                or await beta.capacity_used(db) >= beta.wave_capacity(campaign)):
            raise HTTPException(409, "Aucune place disponible pour rétablir cette invitation.")
        row.revoked_at = None
    await db.commit()
    return await beta.serialize_enrollment(db, row)


@router.get("/api/beta/me")
async def me(user: User = Depends(require_auth), db: AsyncSession = Depends(get_db)):
    row = await beta.enrollment_for(db, user)
    if row and row.activated_at and row.user_id != user.id:
        row = None
    campaign = await beta.campaign_row(db)
    application = await beta_applications.for_user(db, user)
    return {"enrollment": await beta.serialize_enrollment(db, row) if row else None,
            "application": beta_applications.serialize(application) if application else None,
            "campaign_name": campaign.name if campaign else None,
            "access_days": campaign.access_days if campaign else None,
            "can_activate": bool(row and row.activated_at is None and not row.revoked_at
                                 and campaign and beta.recruitment_open(campaign)),
            "email_verified": user.email_verified}


@router.post("/api/beta/activate")
async def activate(user: User = Depends(require_auth), db: AsyncSession = Depends(get_db)):
    row = await beta.activate(db, user)
    await db.commit()
    return await beta.serialize_enrollment(db, row)
