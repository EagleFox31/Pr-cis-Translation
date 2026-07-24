"""Journal central des erreurs — table error_logs

Capte toutes les erreurs (frontend, backend, API) en un seul endroit. La colonne
`fingerprint` (indexée) sert au regroupement des occurrences identiques ;
`status` (new/handled) au cycle « consigner puis supprimer ».

Revision ID: 0006_error_logs
Revises: 0005_pages_done
Create Date: 2026-07-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0006_error_logs"
down_revision: Union[str, None] = "0005_pages_done"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "error_logs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("source", sa.String(16), nullable=False, index=True),
        sa.Column("level", sa.String(16), nullable=False, server_default="error", index=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("stack", sa.Text(), nullable=True),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("user_id", sa.String(32),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("user_email", sa.String(255), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=False, index=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="new", index=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("error_logs")
