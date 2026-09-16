"""Ajoute la nature métier des mouvements sans altérer les quantités existantes."""
from alembic import op
import sqlalchemy as sa

revision = "20260728_07"
down_revision = "20260728_06"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("stock_movements", sa.Column("movement_type", sa.String(40), nullable=True))
    op.execute("""UPDATE stock_movements SET movement_type = CASE
        WHEN reference_type = 'purchase' THEN 'ENTREE_ACHAT'
        WHEN reference_type = 'customer_order' THEN 'SORTIE_COMMANDE_CLIENT'
        WHEN type = 'IN' THEN 'AJUSTEMENT_POSITIF'
        WHEN type = 'OUT' THEN 'AJUSTEMENT_NEGATIF'
        ELSE 'INVENTAIRE' END""")
    op.create_index("ix_stock_movements_movement_type", "stock_movements", ["movement_type"])


def downgrade():
    op.drop_index("ix_stock_movements_movement_type", table_name="stock_movements")
    op.drop_column("stock_movements", "movement_type")
