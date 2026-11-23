"""Copie d'admin : lien d'un document vers le document client dont il est la copie."""
from alembic import op
import sqlalchemy as sa

revision = "0025_copie_admin"
down_revision = "0024_nouveautes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("copie_de", sa.String(32), nullable=True))
    op.create_index("ix_documents_copie_de", "documents", ["copie_de"])


def downgrade():
    op.drop_index("ix_documents_copie_de", table_name="documents")
    op.drop_column("documents", "copie_de")
