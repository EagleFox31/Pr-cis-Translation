"""Applications for the existing beta pilot; recruitment stays closed."""
from alembic import op
import sqlalchemy as sa

revision = "0011_beta_applications"
down_revision = "0010_beta_program"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "beta_applications",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("campaign_id", sa.String(32), sa.ForeignKey("beta_campaigns.id"), nullable=False),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("primary_format", sa.String(8), nullable=False),
        sa.Column("motivation", sa.Text(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewer_id", sa.String(32), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.UniqueConstraint("campaign_id", "email", name="uq_beta_application_email"),
        sa.UniqueConstraint("campaign_id", "user_id", name="uq_beta_application_user"),
    )


def downgrade():
    op.drop_table("beta_applications")
