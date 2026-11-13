"""Nouveautés : date de dernière consultation, abonnement e-mail, langue ; registre des envois."""
from alembic import op
import sqlalchemy as sa

revision = "0024_nouveautes"
down_revision = "0023_extension_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("nouveautes_vues_le", sa.DateTime(timezone=True),
                                     nullable=True))
    op.add_column("users", sa.Column("abonne_nouveautes", sa.Boolean(), nullable=False,
                                     server_default=sa.false()))
    op.add_column("users", sa.Column("abonne_nouveautes_le", sa.DateTime(timezone=True),
                                     nullable=True))
    op.add_column("users", sa.Column("langue", sa.String(5), nullable=False,
                                     server_default="fr"))
    op.create_table(
        "nouveautes_envois",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("envoye_le", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "version", name="uq_nouveautes_envois_user_version"),
    )
    op.create_index("ix_nouveautes_envois_user_id", "nouveautes_envois", ["user_id"])


def downgrade():
    op.drop_index("ix_nouveautes_envois_user_id", table_name="nouveautes_envois")
    op.drop_table("nouveautes_envois")
    op.drop_column("users", "langue")
    op.drop_column("users", "abonne_nouveautes_le")
    op.drop_column("users", "abonne_nouveautes")
    op.drop_column("users", "nouveautes_vues_le")
