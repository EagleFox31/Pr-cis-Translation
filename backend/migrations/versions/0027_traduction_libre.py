"""Traduction libre : pages traduites en aperçu sans solde, et leur plafond.

`documents.pages_libres` : pages d'un document non couvertes par un forfait ou
un solde ; tant qu'il en reste, pas de téléchargement ni de lecture en clair.
`libre_grants` : trace des pages libres par compte et par appareil (plafond sur
24 h), purgée après 2 jours (docs/etude-traduction-libre.md)."""
from alembic import op
import sqlalchemy as sa

revision = "0027_traduction_libre"
down_revision = "0026_pages_offertes_en_clair"
branch_labels = None
depends_on = None


# Instructions idempotentes : la colonne et la table peuvent déjà exister sur
# une base où elles ont été posées avant le passage de cette révision.
DDL = [
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS pages_libres INTEGER NOT NULL DEFAULT 0",
    "CREATE TABLE IF NOT EXISTS libre_grants ("
    " id VARCHAR(32) PRIMARY KEY,"
    " user_id VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,"
    " machine_id VARCHAR(32),"
    " pages INTEGER NOT NULL,"
    " created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now())",
    "CREATE INDEX IF NOT EXISTS ix_libre_grants_user_id ON libre_grants (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_libre_grants_machine_recent ON libre_grants (machine_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_libre_grants_user_recent ON libre_grants (user_id, created_at)",
]


def upgrade():
    for instruction in DDL:
        op.execute(instruction)


def downgrade():
    op.drop_index("ix_libre_grants_user_recent", table_name="libre_grants")
    op.drop_index("ix_libre_grants_machine_recent", table_name="libre_grants")
    op.drop_index("ix_libre_grants_user_id", table_name="libre_grants")
    op.drop_table("libre_grants")
    op.drop_column("documents", "pages_libres")
