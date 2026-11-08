"""Extension: permanent counters per user and page."""
from alembic import op
import sqlalchemy as sa

revision = "0020_extension_usage"
down_revision = "0019_extension_avance"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "extension_usage",
        sa.Column("user_id", sa.String(32),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("page", sa.String(64), primary_key=True),
        sa.Column("caracteres", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("images", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jour", sa.Date(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_extension_usage_jour", "extension_usage", ["user_id", "jour"])


def downgrade():
    op.drop_index("ix_extension_usage_jour", table_name="extension_usage")
    op.drop_table("extension_usage")
