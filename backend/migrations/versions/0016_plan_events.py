"""Historique des forfaits : table `plan_events`

Reprise : une ligne par paiement de forfait réussi et appliqué (non marqué à
rembourser). Un paiement du même plan que le précédent du compte compte comme
renouvellement. Les attributions par l'administration et les échéances passées
ne laissaient aucune trace : elles sont tracées à partir de cette migration.

Revision ID: 0016_plan_events
Revises: 0015_beta_mailbox_unique
Create Date: 2026-10-25
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa

revision: str = "0016_plan_events"
down_revision: Union[str, None] = "0015_beta_mailbox_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    events = op.create_table(
        "plan_events",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False),
        sa.Column("months", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_id", sa.String(32), sa.ForeignKey("payments.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_plan_events_user_id", "plan_events", ["user_id"])

    payments = sa.table("payments", sa.column("id", sa.String(32)),
                        sa.column("user_id", sa.String(32)), sa.column("plan", sa.String(20)),
                        sa.column("months", sa.Integer()), sa.column("status", sa.String(20)),
                        sa.column("credited", sa.Boolean()), sa.column("refund_due", sa.Boolean()),
                        sa.column("created_at", sa.DateTime(timezone=True)))
    rows = op.get_bind().execute(
        sa.select(payments.c.id, payments.c.user_id, payments.c.plan, payments.c.months,
                  payments.c.created_at)
        .where(payments.c.plan.is_not(None), payments.c.status == "SUCCESSFUL",
               payments.c.credited.is_(True), payments.c.refund_due.is_(False))
        .order_by(payments.c.user_id, payments.c.created_at)).mappings().all()
    last_plan: dict[str, str] = {}
    backfill = []
    for row in rows:
        kind = "renewal" if last_plan.get(row["user_id"]) == row["plan"] else "subscription"
        last_plan[row["user_id"]] = row["plan"]
        backfill.append({"id": uuid.uuid4().hex, "user_id": row["user_id"], "kind": kind,
                         "plan": row["plan"], "months": row["months"], "expires_at": None,
                         "payment_id": row["id"], "created_at": row["created_at"]})
    if backfill:
        op.bulk_insert(events, backfill)


def downgrade() -> None:
    op.drop_index("ix_plan_events_user_id", table_name="plan_events")
    op.drop_table("plan_events")
