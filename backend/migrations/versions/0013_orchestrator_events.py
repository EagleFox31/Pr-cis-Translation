"""Durable, duplicate-safe payment orchestrator notifications; never credit here."""
from alembic import op
import sqlalchemy as sa

revision = "0013_orchestrator_events"
down_revision = "0012_beta_abuse_guards"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payment_orchestrator_events",
        sa.Column("event_id", sa.String(160), primary_key=True),
        sa.Column("project_id", sa.String(160), nullable=False),
        sa.Column("environment", sa.String(8), nullable=False),
        sa.Column("effect_key", sa.String(160), nullable=False),
        sa.Column("payment_id", sa.String(160), nullable=False),
        sa.Column("merchant_id", sa.String(160), nullable=False),
        sa.Column("external_reference", sa.String(160), nullable=False),
        sa.Column("provider_reference", sa.String(160), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("state", sa.String(24), nullable=False,
                  server_default="pending_purchase_match"),
        sa.Column("received_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("project_id", "environment", "effect_key",
                            name="uq_orchestrator_payment_effect"),
        sa.CheckConstraint("amount_minor >= 100", name="ck_orchestrator_amount_min"),
        sa.CheckConstraint("environment IN ('sandbox','live')",
                           name="ck_orchestrator_environment"),
    )
    op.create_index("ix_orchestrator_payment_project",
                    "payment_orchestrator_events", ["project_id"])


def downgrade():
    op.drop_index("ix_orchestrator_payment_project",
                  table_name="payment_orchestrator_events")
    op.drop_table("payment_orchestrator_events")
