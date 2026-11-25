"""Extension: connexion par le site (codes à usage unique) et client des sessions."""
from alembic import op
import sqlalchemy as sa

revision = "0023_extension_auth"
down_revision = "0022_extension_textes_vus"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "extension_auth_codes",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(32),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_challenge", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_extension_auth_codes_code_hash", "extension_auth_codes",
                    ["code_hash"], unique=True)
    op.create_index("ix_extension_auth_codes_user_id", "extension_auth_codes",
                    ["user_id"])
    op.add_column("refresh_tokens",
                  sa.Column("client", sa.String(16), nullable=False,
                            server_default="site"))


def downgrade():
    op.drop_column("refresh_tokens", "client")
    op.drop_index("ix_extension_auth_codes_user_id", table_name="extension_auth_codes")
    op.drop_index("ix_extension_auth_codes_code_hash", table_name="extension_auth_codes")
    op.drop_table("extension_auth_codes")
