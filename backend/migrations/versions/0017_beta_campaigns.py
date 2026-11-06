"""Plusieurs programmes bêta : un seul ouvert à la fois

Les identifiants des nouveaux programmes sont générés par l'application ; la
ligne `pilot` existante est conservée telle quelle. L'index partiel garantit
qu'un seul programme est ouvert aux candidatures à un instant donné.

Revision ID: 0017_beta_campaigns
Revises: 0016_plan_events
Create Date: 2026-10-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0017_beta_campaigns"
down_revision: Union[str, None] = "0016_plan_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("uq_beta_campaign_open", "beta_campaigns", ["state"], unique=True,
                    postgresql_where=sa.text("state = 'open'"), sqlite_where=sa.text("state = 'open'"))


def downgrade() -> None:
    op.drop_index("uq_beta_campaign_open", table_name="beta_campaigns")
