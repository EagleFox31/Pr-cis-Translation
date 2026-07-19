"""documents.pages_done — l'avancement survit à la session

L'avancement d'une traduction vivait UNIQUEMENT dans le dictionnaire `_jobs`,
en mémoire du processus. Conséquences : invisible depuis une autre session,
perdu au redémarrage, et impossible à retrouver après une reconnexion. La
traduction, elle, continuait de tourner — seule sa progression était
inobservable, ce qui revenait pour l'utilisateur à ne pas savoir si son
document avançait encore.

`pages_done` la met en base : le nombre de pages terminées, à comparer à
`page_count`. Toute session, à tout moment, peut donc reconstituer l'état.

Backfill : 0. Pour les documents déjà `done`, l'interface lit `status` et non
le compteur — un 0 sur un document terminé n'affiche rien de faux.

Revision ID: 0005_pages_done
Revises: 0004_payments
Create Date: 2026-07-20
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0005_pages_done"
down_revision: Union[str, None] = "0004_payments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("pages_done", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("documents", "pages_done")
