"""Réduit le workflow achat aux cinq statuts officiels."""
from alembic import op

revision = "20260731_13"
down_revision = "20260731_12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""UPDATE purchases SET status=CASE status
      WHEN 'draft' THEN 'EN_PREPARATION' WHEN 'ordered' THEN 'COMMANDE_ENVOYEE'
      WHEN 'supplier_accepted' THEN 'CONFIRMEE_PAR_FOURNISSEUR'
      WHEN 'supplier_confirmed' THEN 'CONFIRMEE_PAR_FOURNISSEUR'
      WHEN 'awaiting_receipt' THEN 'CONFIRMEE_PAR_FOURNISSEUR'
      WHEN 'partially_received' THEN 'CONFIRMEE_PAR_FOURNISSEUR'
      WHEN 'received' THEN 'RECEPTIONNEE' WHEN 'cancelled' THEN 'ANNULEE'
      ELSE status END""")


def downgrade() -> None:
    op.execute("""UPDATE purchases SET status=CASE status
      WHEN 'EN_PREPARATION' THEN 'draft' WHEN 'COMMANDE_ENVOYEE' THEN 'ordered'
      WHEN 'CONFIRMEE_PAR_FOURNISSEUR' THEN 'supplier_accepted'
      WHEN 'RECEPTIONNEE' THEN 'received' WHEN 'ANNULEE' THEN 'cancelled'
      ELSE status END""")
