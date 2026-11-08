"""Extension: fingerprints of texts already counted, per user."""
from alembic import op
import sqlalchemy as sa

revision = "0021_extension_textes_vus"
down_revision = "0020_extension_usage"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "extension_textes_vus",
        sa.Column("user_id", sa.String(32),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("empreinte", sa.String(64), primary_key=True),
        sa.Column("jour", sa.Date(), nullable=False),
    )
    op.create_index("ix_extension_textes_vus_jour", "extension_textes_vus", ["jour"])


def downgrade():
    op.drop_index("ix_extension_textes_vus_jour", table_name="extension_textes_vus")
    op.drop_table("extension_textes_vus")
