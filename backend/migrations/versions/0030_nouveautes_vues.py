"""Nouveautés : identifiants déjà montrés, par compte.

`users.nouveautes_vues` (JSON, liste d'identifiants du catalogue) : une
nouveauté s'affiche tant que son identifiant n'y figure pas, quelle que soit
la date écrite au catalogue. NULL = compte antérieur (règle de transition dans
services/nouveautes.py). Colonne nullable, aucune réécriture."""
from alembic import op

revision = "0030_nouveautes_vues"
down_revision = "0029_admin_recaps"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS nouveautes_vues JSON")


def downgrade():
    op.drop_column("users", "nouveautes_vues")
