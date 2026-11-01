"""Extension: characters already paid for and not yet used, per user."""
from alembic import op
import sqlalchemy as sa

revision = "0013_extension_avance"
down_revision = "0012_beta_abuse_guards"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("extension_avance", sa.Integer(),
                                     nullable=False, server_default="0"))


def downgrade():
    op.drop_column("users", "extension_avance")
