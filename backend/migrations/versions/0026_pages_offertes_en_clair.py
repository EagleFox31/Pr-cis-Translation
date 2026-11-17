"""Pages offertes en clair : débloque les anciens documents traduits avec les
pages offertes du forfait Gratuit (docs/etude-traduction-libre.md, règle a).

Jusqu'ici, un document traduit avec les seules pages offertes gardait
`paid = false`. Ces pages étaient couvertes par un forfait : elles deviennent
téléchargeables, comme le promet la carte Gratuit. Les autres documents non
payés (anciens aperçus verrouillés, sans consommation) restent verrouillés."""
from alembic import op

revision = "0026_pages_offertes_en_clair"
down_revision = "0025_copie_admin"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE documents SET paid = true
        WHERE paid = false
          AND EXISTS (SELECT 1 FROM usage_records u
                      WHERE u.document_id = documents.id
                        AND u.kind IN ('free_offer', 'legacy')
                        AND u.refunded = false)
    """)


def downgrade():
    # Irréversible : on ne sait plus quels documents étaient verrouillés.
    pass
