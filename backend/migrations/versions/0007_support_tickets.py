"""Demandes d'assistance — table support_tickets

Ce que les utilisateurs ÉCRIVENT (signaler un problème, aide sur l'abonnement),
distinct du journal d'erreurs qui capte ce que la MACHINE constate. `status`
(open/handled) porte le cycle « traiter puis supprimer ».

Revision ID: 0007_support_tickets
Revises: 0006_error_logs
Create Date: 2026-07-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0007_support_tickets"
down_revision: Union[str, None] = "0006_error_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("category", sa.String(16), nullable=False, server_default="problem", index=True),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("user_id", sa.String(32),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("user_email", sa.String(255), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open", index=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("support_tickets")
