"""Invitation-only beta program; no campaign or participant is activated."""
from alembic import op
import sqlalchemy as sa

revision = "0010_beta_program"
down_revision = "0009_abonnements"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "beta_campaigns",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("first_wave_capacity", sa.Integer(), nullable=False),
        sa.Column("access_days", sa.Integer(), nullable=False),
        sa.Column("limits", sa.JSON(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("recruitment_ends_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "beta_enrollments",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("campaign_id", sa.String(32), sa.ForeignKey("beta_campaigns.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("primary_format", sa.String(8), nullable=False),
        sa.Column("limits", sa.JSON(), nullable=False),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("campaign_id", "email", name="uq_beta_campaign_email"),
        sa.UniqueConstraint("campaign_id", "user_id", name="uq_beta_campaign_user"),
    )
    for column in ("campaign_id", "email", "user_id"):
        op.create_index(f"ix_beta_enrollments_{column}", "beta_enrollments", [column])
    op.create_table(
        "beta_usage",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("enrollment_id", sa.String(32), sa.ForeignKey("beta_enrollments.id"), nullable=False),
        sa.Column("document_id", sa.String(32), sa.ForeignKey("documents.id", ondelete="SET NULL"), unique=True),
        sa.Column("document_key", sa.String(32), nullable=False, unique=True),
        sa.Column("format", sa.String(8), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("words", sa.Integer(), nullable=False),
        sa.Column("refunded", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("units >= 0 AND words >= 0", name="ck_beta_usage_nonnegative"),
    )
    op.create_index("ix_beta_usage_enrollment_id", "beta_usage", ["enrollment_id"])
    op.create_index("ix_beta_usage_document_id", "beta_usage", ["document_id"])
    op.create_index("ix_beta_usage_document_key", "beta_usage", ["document_key"])


def downgrade():
    op.drop_table("beta_usage")
    op.drop_table("beta_enrollments")
    op.drop_table("beta_campaigns")
