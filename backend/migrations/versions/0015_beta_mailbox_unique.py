"""Une seule inscription bêta activée par boîte e-mail, garantie par la base

Index unique partiel `(campaign_id, mailbox_key) WHERE activated_at IS NOT NULL`.
Les doublons historiques (alias activés avant 0012) gardent leur ligne : seule
la plus ancienne conserve sa clé, les autres repassent à NULL. `mailbox_match`
recalcule alors la clé depuis l'e-mail, donc ces lignes bloquent toujours.

Revision ID: 0015_beta_mailbox_unique
Revises: 0014_anti_abus
Create Date: 2026-10-25
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0015_beta_mailbox_unique"
down_revision: Union[str, None] = "0014_anti_abus"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WHERE = sa.text("activated_at IS NOT NULL")


def upgrade() -> None:
    table = sa.table("beta_enrollments", sa.column("id", sa.String(32)),
                     sa.column("campaign_id", sa.String(32)), sa.column("mailbox_key", sa.String(255)),
                     sa.column("activated_at", sa.DateTime(timezone=True)))
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(table.c.id, table.c.campaign_id, table.c.mailbox_key)
        .where(table.c.activated_at.is_not(None), table.c.mailbox_key.is_not(None))
        .order_by(table.c.activated_at, table.c.id)).mappings().all()
    seen = set()
    for row in rows:
        key = (row["campaign_id"], row["mailbox_key"])
        if key in seen:
            connection.execute(table.update().where(table.c.id == row["id"]).values(mailbox_key=None))
        seen.add(key)
    op.create_index("uq_beta_enrollment_activated_mailbox", "beta_enrollments",
                    ["campaign_id", "mailbox_key"], unique=True,
                    postgresql_where=_WHERE, sqlite_where=_WHERE)


def downgrade() -> None:
    op.drop_index("uq_beta_enrollment_activated_mailbox", table_name="beta_enrollments")
