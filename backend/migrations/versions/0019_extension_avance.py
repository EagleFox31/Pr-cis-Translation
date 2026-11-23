"""Extension: characters already paid for and not yet used, per user."""
from alembic import op

revision = "0019_extension_avance"
down_revision = "0018_document_reglages"
branch_labels = None
depends_on = None


def upgrade():
    # Sans effet si la colonne existe déjà : une base passée par une autre
    # branche peut l'avoir reçue avant que les suites soient remises bout à bout.
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS "
               "extension_avance INTEGER NOT NULL DEFAULT 0")


def downgrade():
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS extension_avance")
