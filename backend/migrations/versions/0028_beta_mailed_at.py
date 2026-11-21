"""Invitation bêta : date du dernier mail d'invitation réellement parti.

`beta_enrollments.mailed_at` reste vide tant qu'aucun mail n'est parti ; l'admin
voit alors les invitations à renvoyer (docs/etude-mail-invitation-beta.md)."""
from alembic import op

revision = "0028_beta_mailed_at"
down_revision = "0027_traduction_libre"
branch_labels = None
depends_on = None


def upgrade():
    # Idempotent, like 0027: the column may already exist on a base created from the models.
    op.execute("ALTER TABLE beta_enrollments ADD COLUMN IF NOT EXISTS mailed_at TIMESTAMP WITH TIME ZONE")


def downgrade():
    op.drop_column("beta_enrollments", "mailed_at")
