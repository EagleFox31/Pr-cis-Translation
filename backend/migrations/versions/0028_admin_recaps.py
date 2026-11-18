"""Récapitulatif quotidien des admins : un enregistrement par jour envoyé.

`admin_recaps.jour` (clé primaire) empêche d'envoyer deux fois le récapitulatif
d'un même jour (docs/etude-retours-18-11.md §2)."""
from alembic import op

revision = "0028_admin_recaps"
down_revision = "0027_traduction_libre"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE TABLE IF NOT EXISTS admin_recaps ("
        " jour DATE PRIMARY KEY,"
        " envoye_le TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now())"
    )


def downgrade():
    op.drop_table("admin_recaps")
