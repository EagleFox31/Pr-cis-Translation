"""Invitations à découvrir Précis — table invitations

Trace de chaque e-mail d'invitation envoyé : sert de garde contre l'abus (quota
quotidien par compte, pas deux invitations à la même adresse trop rapprochées).

Revision ID: 0013_invitations
Revises: 0012_beta_abuse_guards
Create Date: 2026-10-20
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0013_invitations"
down_revision: Union[str, None] = "0012_beta_abuse_guards"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("inviter_id", sa.String(32),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("invitations")
