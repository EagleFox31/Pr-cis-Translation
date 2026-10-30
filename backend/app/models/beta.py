"""Invitation-only beta allowances, independent of subscription credits."""
from datetime import datetime
from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, new_uuid, utcnow


class BetaCampaign(Base):
    __tablename__ = "beta_campaigns"
    __table_args__ = (
        # One program open to applications at a time.
        Index("uq_beta_campaign_open", "state", unique=True,
              postgresql_where=text("state = 'open'"), sqlite_where=text("state = 'open'")),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    first_wave_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    access_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    limits: Mapped[dict] = mapped_column(JSON, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recruitment_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BetaEnrollment(Base):
    __tablename__ = "beta_enrollments"
    __table_args__ = (
        UniqueConstraint("campaign_id", "email", name="uq_beta_campaign_email"),
        UniqueConstraint("campaign_id", "user_id", name="uq_beta_campaign_user"),
        Index("ix_beta_enrollment_mailbox", "campaign_id", "mailbox_key"),
        # One activated trial per mailbox, enforced by the database as well.
        Index("uq_beta_enrollment_activated_mailbox", "campaign_id", "mailbox_key", unique=True,
              postgresql_where=text("activated_at IS NOT NULL"),
              sqlite_where=text("activated_at IS NOT NULL")),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    campaign_id: Mapped[str] = mapped_column(String(32), ForeignKey("beta_campaigns.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    mailbox_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    primary_format: Mapped[str] = mapped_column(String(8), nullable=False, default="pdf")
    limits: Mapped[dict] = mapped_column(JSON, nullable=False)
    invited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BetaUsage(Base):
    __tablename__ = "beta_usage"
    __table_args__ = (CheckConstraint("units >= 0 AND words >= 0", name="ck_beta_usage_nonnegative"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    enrollment_id: Mapped[str] = mapped_column(String(32), ForeignKey("beta_enrollments.id"), nullable=False, index=True)
    document_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("documents.id", ondelete="SET NULL"), unique=True, index=True)
    document_key: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    words: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    refunded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BetaApplication(Base):
    __tablename__ = "beta_applications"
    __table_args__ = (
        UniqueConstraint("campaign_id", "email", name="uq_beta_application_email"),
        UniqueConstraint("campaign_id", "user_id", name="uq_beta_application_user"),
        Index("ix_beta_application_mailbox", "campaign_id", "mailbox_key"),
        Index("ix_beta_application_ip_recent", "campaign_id", "ip_hash", "submitted_at"),
        Index("ix_beta_application_device_recent", "campaign_id", "device_hash", "submitted_at"),
        Index("ix_beta_application_signal_age", "submitted_at"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    campaign_id: Mapped[str] = mapped_column(String(32), ForeignKey("beta_campaigns.id"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id", ondelete="SET NULL"))
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    mailbox_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    primary_format: Mapped[str] = mapped_column(String(8), nullable=False)
    motivation: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewer_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id", ondelete="SET NULL"))
