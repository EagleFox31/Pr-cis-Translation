"""Réglages d'origine d'une traduction, pour la reprendre à l'identique

Revision ID: 0018_document_reglages
Revises: 0017_beta_campaigns
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0018_document_reglages"
down_revision: Union[str, None] = "0017_beta_campaigns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("reglages", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "reglages")
