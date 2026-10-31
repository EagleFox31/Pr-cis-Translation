"""Anti-abus des pages offertes — device_links, free_grants, téléphone vérifié

`device_links` relie les identifiants d'un même appareil (cookie, copie locale,
empreinte) à une machine ; `free_grants` trace les pages offertes attribuées.
Uniquement des empreintes HMAC, purgées automatiquement. Les colonnes
`users.phone_*` servent à exempter un compte vérifié de la zone grise ; aucun
fournisseur SMS n'est branché à ce stade.

Revision ID: 0014_anti_abus
Revises: 0013_invitations
Create Date: 2026-10-22
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0014_anti_abus"
down_revision: Union[str, None] = "0013_invitations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_links",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("hash", sa.String(64), nullable=False, unique=True),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("machine_id", sa.String(32), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now(), index=True),
    )
    op.create_table(
        "free_grants",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("machine_id", sa.String(32), nullable=True),
        sa.Column("ip_hash", sa.String(64), nullable=True),
        sa.Column("mailbox_key", sa.String(64), nullable=True),
        sa.Column("pages", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_free_grants_machine_recent", "free_grants", ["machine_id", "created_at"])
    op.create_index("ix_free_grants_ip_recent", "free_grants", ["ip_hash", "created_at"])
    op.create_index("ix_free_grants_mailbox_recent", "free_grants", ["mailbox_key", "created_at"])
    op.create_index("ix_free_grants_created_at", "free_grants", ["created_at"])

    op.add_column("users", sa.Column("phone_hash", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("phone_verified_at", sa.DateTime(timezone=True),
                                     nullable=True))
    op.create_index("ix_users_phone_hash", "users", ["phone_hash"], unique=True)

    # Les alias étendus (+tag Outlook/iCloud/Proton/Fastmail, -suffixe Yahoo)
    # changent la clé de boîte : recalculée sur les lignes bêta non anonymisées,
    # sinon un ancien « nom+1@outlook.com » échapperait au dédoublonnage.
    from app.services.beta_abuse import ANONYMOUS, canonical_mailbox
    bind = op.get_bind()
    for table in ("beta_enrollments", "beta_applications"):
        rows = bind.execute(sa.text(
            f"SELECT id, email, mailbox_key FROM {table} WHERE email IS NOT NULL")).all()
        for row_id, email, key in rows:
            if key and key.startswith(ANONYMOUS):
                continue
            fresh = canonical_mailbox(email)
            if fresh != key:
                bind.execute(sa.text(f"UPDATE {table} SET mailbox_key = :k WHERE id = :i"),
                             {"k": fresh, "i": row_id})


def downgrade() -> None:
    op.drop_index("ix_users_phone_hash", table_name="users")
    op.drop_column("users", "phone_verified_at")
    op.drop_column("users", "phone_hash")
    for name in ("ix_free_grants_created_at", "ix_free_grants_mailbox_recent",
                 "ix_free_grants_ip_recent", "ix_free_grants_machine_recent"):
        op.drop_index(name, table_name="free_grants")
    op.drop_table("free_grants")
    op.drop_table("device_links")
