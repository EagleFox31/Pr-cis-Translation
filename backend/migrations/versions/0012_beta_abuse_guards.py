"""Beta mailbox keys and short-lived network/browser digests; no new access."""
from alembic import op
import sqlalchemy as sa

revision = "0012_beta_abuse_guards"
down_revision = "0011_beta_applications"
branch_labels = None
depends_on = None

_INDEXES = [
    ("ix_beta_enrollment_mailbox", "beta_enrollments", ["campaign_id", "mailbox_key"]),
    ("ix_beta_application_mailbox", "beta_applications", ["campaign_id", "mailbox_key"]),
    ("ix_beta_application_ip_recent", "beta_applications", ["campaign_id", "ip_hash", "submitted_at"]),
    ("ix_beta_application_device_recent", "beta_applications", ["campaign_id", "device_hash", "submitted_at"]),
    ("ix_beta_application_signal_age", "beta_applications", ["submitted_at"]),
]


def _mailbox(email):
    # Frozen migration rule, independent of future application code.
    address = email.strip().casefold()
    local, separator, domain = address.rpartition("@")
    if separator and domain in ("gmail.com", "googlemail.com"):
        return local.split("+", 1)[0].replace(".", "") + "@gmail.com"
    return address


def upgrade():
    for name in ("beta_applications", "beta_enrollments"):
        op.add_column(name, sa.Column("mailbox_key", sa.String(255), nullable=True))
        op.add_column(name, sa.Column("ip_hash", sa.String(64), nullable=True))
        op.add_column(name, sa.Column("device_hash", sa.String(64), nullable=True))
        table = sa.table(name, sa.column("id", sa.String(32)),
                         sa.column("email", sa.String(255)), sa.column("mailbox_key", sa.String(255)))
        connection = op.get_bind()
        for row in connection.execute(sa.select(table.c.id, table.c.email)).mappings().all():
            connection.execute(table.update().where(table.c.id == row["id"])
                               .values(mailbox_key=_mailbox(row["email"])))
    # Non-unique: historical aliases remain intact and are flagged for review.
    # New admissions/invitations serialize on the existing campaign lock.
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade():
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
    for table in ("beta_applications", "beta_enrollments"):
        for column in ("device_hash", "ip_hash", "mailbox_key"):
            op.drop_column(table, column)
